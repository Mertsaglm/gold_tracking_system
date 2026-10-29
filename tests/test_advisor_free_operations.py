"""2026-10-28 üretim hataları: maliyet/veri ayrımı ve kayıpsız küçük arşiv."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import gzip
import importlib.metadata
import json
import zipfile

import pytest
import requests

from advisor import capsule, engine, marketdata, recovery, service, watchdog
from advisor.ledger import Ledger, canonical, digest, fund
from tests.advisor_legacy import legacy_configuration
from tests.test_advisor_operations import archive

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,16,12,tzinfo=timezone.utc)


def inputs(tmp_path):
    cfg={**legacy_configuration(ROOT),'market':'gold'}
    ledger=Ledger(tmp_path/'events.jsonl');fund(ledger,cfg,'2026-09-15',NOW.isoformat())
    row={'symbol':'GRAM','date':'2026-09-15','close':100,'quality_ok':True,
         'trend50':5,'rsi14':50,'volatility20':1}
    quote={'symbol':'GRAM','bid':100,'ask':114,'quoted_at':NOW.isoformat(),
           'reference_price':100,'source':'fixture'}
    return cfg,ledger,row,quote


def test_spread_is_a_cost_block_and_missing_data_remains_an_error(tmp_path):
    cfg,ledger,row,q=inputs(tmp_path)
    decisions,fills=engine.run(ledger,[row],{'GRAM':20},{'ready':True},cfg,{'GRAM':q},NOW)
    d,=decisions
    assert not fills and (d['action'],d['code'])==('BEKLE','spread_limit')
    assert next(c for c in d['checks'] if c['check']=='veri')['status']=='geçti'
    assert next(c for c in d['checks'] if c['check']=='makas')['status']=='kaldı'
    for quotes, changed_row in [({},row),({'GRAM':{**q,'quoted_at':(NOW-timedelta(hours=1)).isoformat()}},row),
                                 ({'GRAM':q},{**row,'quality_ok':False})]:
        ds,fs=engine.run(ledger,[changed_row],{'GRAM':20},{'ready':True},cfg,quotes,NOW)
        assert not fs and ds[0]['action']=='VERİ BEKLENİYOR'


def test_spread_does_not_disable_existing_stop(tmp_path):
    cfg,ledger,row,q=inputs(tmp_path)
    ledger.add('fill','owned',NOW.isoformat(),book='strategy',symbol='GRAM',side='BUY',
               quantity='1',price=100,notional_cents=10000,fee_cents=0,stop=101,target=120)
    ds,fs=engine.run(ledger,[row],{'GRAM':20},{'ready':True},cfg,{'GRAM':q},NOW)
    assert ds[0]['action']=='SAT' and fs[0]['reason']=='stop'
    assert not ledger.account()['positions']


def test_source_retry_recovers_and_never_logs_secret_exception_text(monkeypatch):
    calls=[];sleeps=[]
    def get(*a,**k):
        calls.append(1)
        if len(calls)<3:raise requests.ReadTimeout('token=must-not-appear')
        return type('Response',(),{'text':'ok','raise_for_status':lambda self:None})()
    monkeypatch.setattr(marketdata.requests,'get',get)
    monkeypatch.setattr(marketdata.time,'sleep',sleeps.append)
    assert marketdata.fetch_page('https://fixture.invalid')=='ok'
    assert len(calls)==3 and sleeps==[.5,1.]
    calls.clear()
    def fail(*a,**k):calls.append(1);raise requests.ReadTimeout('token=must-not-appear')
    monkeypatch.setattr(marketdata.requests,'get',fail)
    with pytest.raises(marketdata.SourceError) as exc:marketdata.fetch_page('https://fixture.invalid')
    assert len(calls)==3 and str(exc.value)=='http: ReadTimeout'
    assert 'must-not-appear' not in str(exc.value)


def test_permanent_http_and_parser_errors_are_not_retried(monkeypatch):
    calls=[]
    def get(*a,**k):
        calls.append(1);response=requests.Response();response.status_code=403
        raise requests.HTTPError('token=secret',response=response)
    monkeypatch.setattr(marketdata.requests,'get',get)
    with pytest.raises(marketdata.SourceError,match='HTTP 403'):marketdata.fetch_page('https://fixture.invalid')
    assert len(calls)==1
    monkeypatch.setattr(marketdata,'fetch_page',lambda url:'bad html')
    cfg=legacy_configuration(ROOT);cfg['market']='bist'
    with pytest.raises(marketdata.SourceError,match='stocks_parser'):marketdata.fetch(cfg,['AAA'],NOW)


def test_capsule_v2_reuses_prefix_and_source_and_v1_still_replays(tmp_path):
    cfg,ledger,row,q=inputs(tmp_path);q.update(ask=100)
    # Defter öneki 256 kaydı aştığında ikinci kapsül aynı tam parçayı kullanır.
    for i in range(260):ledger.add('observation',str(i),NOW.isoformat(),number=i)
    model={'ready':True};ctx=capsule.inputs(ledger,[row],{'GRAM':20},model,cfg,{'GRAM':q},NOW)
    ds,_=engine.run(ledger,[row],{'GRAM':20},model,cfg,{'GRAM':q},NOW)
    receipt=capsule.save(tmp_path,ctx,ds);path=tmp_path/receipt['path']
    original=copy.deepcopy(ctx)
    assert capsule.reproduce(path)['ok'] and capsule.read(path)['context']==ctx
    ledger.add('observation','later',NOW.isoformat(),number=999)
    second={**ctx,'events':copy.deepcopy(ledger.events)}
    ds2,_=engine.run(ledger,[row],{'GRAM':20},model,cfg,{'GRAM':q},NOW)
    receipt2=capsule.save(tmp_path,second,ds2)
    assert ctx==original
    assert len(list((tmp_path/'capsules/sources').glob('*.gz')))==1
    assert len(list((tmp_path/'capsules/ledger').glob('*.gz')))==3
    assert capsule.reproduce(tmp_path/receipt2['path'])['ok']
    # Önceki bağımsız v1 biçimi, yeni okuyucuyla da aynı kararı üretir.
    p=capsule.read(path);v1={'schema':1,'context':p['context'],'source':p['source'],
                           'expected':p['expected'],'runtime':p['runtime']}
    legacy=tmp_path/'old.json.gz';legacy.write_bytes(gzip.compress(canonical({'hash':digest(v1),'payload':v1}).encode()))
    assert capsule.reproduce(legacy)['ok']
    ref=json.loads(gzip.decompress(path.read_bytes()))['payload']['context']['events_ref'][0]
    chunk=tmp_path/'capsules/ledger'/(ref+'.json.gz');chunk.write_bytes(gzip.compress(b'[]'))
    with pytest.raises(ValueError,match='mührü'):capsule.reproduce(path)


def test_operational_backup_restores_ledger_but_labels_omitted_replay_history(tmp_path):
    root=tmp_path/'source';root.mkdir();ledger=archive(root)
    directory=root/'data/advisor/capsules';directory.mkdir();(directory/'old.json.gz').write_bytes(b'old-evidence')
    before=(directory/'old.json.gz').read_bytes()
    output=tmp_path/'backup.zip';result=recovery.backup(root,output,operational=True)
    assert result['scope']=='operational'
    with zipfile.ZipFile(output) as z:
        assert json.loads(z.read('backup-info.json'))['capsules_included'] is False
        assert not any('/capsules/' in name for name in z.namelist())
    assert recovery.drill(output)['ledger_hash']==ledger.root_hash
    assert (directory/'old.json.gz').read_bytes()==before


def test_hourly_watchdog_detects_a_missing_hour_without_false_45_minute_alarm(tmp_path):
    archive(tmp_path)
    path=tmp_path/'advisor/config.json';cfg=json.loads(path.read_text())
    cfg.update(cycle_interval_minutes=60,watchdog_max_gap_minutes=90);path.write_text(json.dumps(cfg))
    within=watchdog.inspect(tmp_path,NOW+timedelta(minutes=70))
    assert not any(f['code']=='cycle_gap' for f in within['findings'])
    overdue=watchdog.inspect(tmp_path,NOW+timedelta(minutes=100))
    assert any(f['code']=='cycle_gap' for f in overdue['findings'])


def test_historical_audit_allows_only_spread_diagnosis_not_money_changes(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('audit_production',ROOT/'scripts/audit_production.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    cfg,ledger,row,q=inputs(tmp_path)
    ds,_=engine.run(ledger,[row],{'GRAM':20},{'ready':True},cfg,{'GRAM':q},NOW)
    new={k:v for k,v in ds[0].items() if k not in ('key','decision_key','horizon_sessions')}
    old=copy.deepcopy(new)
    old.update(action='VERİ BEKLENİYOR',code='data_block',decisive_code='data_block',failed_checks=['veri'])
    old['checks'].pop(1);old['checks'][0].update(status='kaldı',note='Banka makası bugün fazla geniş.')
    assert audit.spread_reclassification_only(old,new)
    for key,value in [('target',999999),('symbol','OTHER'),('remaining_forecast_pct',999)]:
        assert not audit.spread_reclassification_only(old,{**new,key:value})
    wrong=copy.deepcopy(new);wrong['checks'][0]['status']='kaldı'
    assert not audit.spread_reclassification_only(old,wrong)


def test_failed_push_rescue_keeps_all_ledgers_and_models_but_not_replay_history(tmp_path):
    import subprocess
    import os
    import sys
    import yaml
    w=yaml.safe_load((ROOT/'.github/workflows/portfolio.yml').read_text())
    steps=w['jobs']['portfolio']['steps']
    command=next(s['run'] for s in steps if s.get('name')=='Arşivi koru')
    rescue=tmp_path/'rescue';source=tmp_path/'data/advisor'
    expected=['accounts/main/events.jsonl','candidates/test/events.jsonl','model.json','latest.json']
    for name in expected+['capsules/old.json.gz','accounts/main/capsules/other.json.gz']:
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
    # Yalnız dış çıktı dizinini testin geçici köküne yönlendir; gerçek adım çalışır.
    result=subprocess.run(['bash','-e','-c',command.replace('/tmp/advisor-delivery',str(rescue))],
                          cwd=tmp_path,capture_output=True,text=True,
                          env={**os.environ,'PATH':str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')})
    assert result.returncode==0,result.stderr
    assert sorted(p.relative_to(rescue).as_posix() for p in rescue.rglob('*') if p.is_file())==sorted(expected)
    assert all((source/name).exists() for name in expected+['capsules/old.json.gz'])
    artifact=next(s for s in steps if str(s.get('uses','')).startswith('actions/upload-artifact'))
    assert '/tmp/advisor-delivery/' in artifact['with']['path']
    assert artifact['with']['retention-days']==3
