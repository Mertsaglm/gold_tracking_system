"""Mühürlü fiyat/model/ayar/kod/girdi paketi ve ağsız karar tekrarı."""
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

from .ledger import atomic_json, canonical, digest


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [clean(v) for v in value]
    if isinstance(value,Decimal):return str(value)
    if hasattr(value,'item'):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def inputs(ledger,rows,forecasts,model,cfg,quotes,now,event_note=None):
    return clean({'events':list(ledger.events),'rows':rows,'forecasts':forecasts,'model':model,'cfg':cfg,
                  'quotes':quotes,'now':now.isoformat(),'event_note':event_note})


def save(state,context,decisions):
    source={p.name:p.read_text() for p in Path(__file__).parent.glob('*.py')}
    runtime={name:importlib.metadata.version(name) for name in ('numpy','pandas','requests','PyYAML')}
    payload={'schema':1,'context':context,'expected':clean(decisions),'source':source,'runtime':runtime}
    key=digest(payload)
    path=Path(state)/'capsules'/(key+'.json.gz')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        # Sonuçların tamamı küçük/tekrarlı JSON; sıkıştırma defter kopyalarının maliyetini azaltır.
        data=gzip.compress(canonical({'hash':key,'payload':payload}).encode(),mtime=0)
        temp=path.with_suffix('.tmp');temp.write_bytes(data);temp.replace(path)
    return {'id':key,'path':'capsules/'+path.name,'code_hash':digest(source),
            'config_hash':digest(context['cfg']),'model_id':context['model'].get('id')}


def reproduce(path):
    envelope=json.loads(gzip.decompress(Path(path).read_bytes()))
    payload=envelope['payload']
    if digest(payload)!=envelope['hash']:raise ValueError('Karar paketi mührü bozuk.')
    for name,version in payload['runtime'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('Paketin kayıtlı bağımlılık sürümleri gerekli: '+name+'=='+version)
    with tempfile.TemporaryDirectory(prefix='advisor-reproduce-') as tmp:
        root=Path(tmp);package=root/'advisor';package.mkdir()
        for name,source in payload['source'].items():
            if Path(name).name!=name or not name.endswith('.py'):raise ValueError('Kod paketinde geçersiz yol.')
            (package/name).write_text(source)
        (root/'input.json').write_text(canonical(payload['context']))
        runner='''import sys,json\nfrom pathlib import Path\nfrom datetime import datetime\nsys.path.insert(0,sys.argv[1])\nfrom advisor.ledger import Ledger,canonical\nfrom advisor.engine import run\np=Path(sys.argv[1]);c=json.loads((p/'input.json').read_text())\nl=Ledger(p/'events.jsonl');l.events=c['events'];l.keys={e['key'] for e in l.events};l.root_hash=l.events[-1]['hash'] if l.events else '0'*64\nd,f=run(l,c['rows'],c['forecasts'],c['model'],c['cfg'],c['quotes'],datetime.fromisoformat(c['now']),c['event_note'])\nprint(canonical(d))\n'''
        result=subprocess.run([sys.executable,'-I','-c',runner,str(root)],capture_output=True,text=True,timeout=60,check=True)
        actual=json.loads(result.stdout)
        if actual!=payload['expected']:raise ValueError('Tekrar üretilen karar kayıtla eşleşmiyor.')
    return {'ok':True,'id':envelope['hash'],'decisions':len(actual),'code_hash':digest(payload['source'])}
