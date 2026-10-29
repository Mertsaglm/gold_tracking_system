"""Mühürlü fiyat/model/ayar/kod/girdi paketi ve ağsız karar tekrarı."""
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import importlib.metadata
import json
import math
import re
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
    # Aynı defter öneki ve kod her kapsülde tekrar kopyalanmaz. Eski v1 dosyaları
    # değişmeden okunur; v2 başvuruları aynı kapsül dizininde mühürlü saklanır.
    store = Path(state) / 'capsules'
    events = context['events']
    refs = [_store_object(store, 'ledger', events[i:i+256]) for i in range(0,len(events),256)]
    compact = {k:v for k,v in context.items() if k!='events'}
    compact['events_ref'] = refs
    compact['events_count'] = len(events)
    payload={'schema':2,'context':compact,'expected':clean(decisions),
             'source_ref':_store_object(store,'sources',source),'runtime':runtime}
    key=digest(payload)
    path=Path(state)/'capsules'/(key+'.json.gz')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        # Sonuçların tamamı küçük/tekrarlı JSON; sıkıştırma defter kopyalarının maliyetini azaltır.
        data=gzip.compress(canonical({'hash':key,'payload':payload}).encode(),mtime=0)
        temp=path.with_suffix('.tmp');temp.write_bytes(data);temp.replace(path)
    return {'id':key,'path':'capsules/'+path.name,'code_hash':digest(source),
            'config_hash':digest(context['cfg']),'model_id':context['model'].get('id')}


def _store_object(store, namespace, data):
    key = digest(data)
    path = store / namespace / (key + '.json.gz')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if json.loads(gzip.decompress(path.read_bytes())) != data:
            raise ValueError('Kapsül ortak nesnesinin mührü bozuk.')
    else:
        temp=path.with_suffix('.tmp')
        temp.write_bytes(gzip.compress(canonical(data).encode(),mtime=0))
        temp.replace(path)
    return key


def _read_object(store, namespace, key):
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):
        raise ValueError('Kapsül başvurusu geçersiz.')
    try:
        data=json.loads(gzip.decompress((store/namespace/(key+'.json.gz')).read_bytes()))
    except (OSError, ValueError, EOFError) as exc:
        raise ValueError('Kapsül ortak nesnesi eksik veya bozuk.') from exc
    if digest(data)!=key:
        raise ValueError('Kapsül ortak nesnesinin mührü bozuk.')
    return data


def read(path):
    """v1/v2 mührünü ve ortak nesneleri doğrulayıp tam girdiyi döndürür."""
    envelope=json.loads(gzip.decompress(Path(path).read_bytes()))
    payload=envelope['payload']
    if digest(payload)!=envelope['hash']:raise ValueError('Karar paketi mührü bozuk.')
    if payload.get('schema') == 2:
        context=dict(payload['context'])
        events=[]
        for key in context.pop('events_ref'):
            events.extend(_read_object(Path(path).parent,'ledger',key))
        if len(events)!=context.pop('events_count'):
            raise ValueError('Kapsül defter uzunluğu doğrulanamadı.')
        context['events']=events
        payload={**payload,'context':context,
                 'source':_read_object(Path(path).parent,'sources',payload['source_ref'])}
    elif payload.get('schema') != 1:
        raise ValueError('Kapsül sürümü desteklenmiyor.')
    return payload


def reproduce(path):
    payload=read(path)
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
    return {'ok':True,'id':json.loads(gzip.decompress(Path(path).read_bytes()))['hash'],
            'decisions':len(actual),'code_hash':digest(payload['source'])}
