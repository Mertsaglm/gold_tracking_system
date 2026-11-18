"""Nöbetçi süreç dışındadır; kurtarma gerçek defter eşliğini sınar."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import zipfile

import pytest

from tests.advisor_legacy import legacy_configuration

from advisor import recovery, service, watchdog
from advisor.ledger import Ledger, fund

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,16,12,tzinfo=timezone.utc)


def archive(root):
    cfg=legacy_configuration(ROOT);cfg['telegram']['enabled']=False
    (root/'advisor').mkdir();(root/'advisor/config.json').write_text(json.dumps(cfg))
    (root/'holidays_tr.yaml').write_text('tam_gun:\n  "2026": []\n')
    p=root/'data/advisor';p.mkdir(parents=True)
    l=Ledger(p/'events.jsonl');fund(l,cfg,'2026-09-15',NOW.isoformat())
    l.add('session_check','check',NOW.isoformat(),valid_quotes=1,expected_quotes=1,decisions=1,corporate_ok=True,errors=[])
    l.save()
    (p/'latest.json').write_text(json.dumps({'generated_at':NOW.isoformat(),'health':{'errors':[],'expected_quotes':1,'ledger_hash':l.root_hash},'quotes':{}}))
    (p/'run_status.json').write_text(json.dumps({'ok':True}))
    return l


def test_watchdog_does_not_write_and_detects_missed_and_failed_cycle(tmp_path):
    archive(tmp_path)
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert watchdog.inspect(tmp_path,NOW)['ok']
    later=watchdog.inspect(tmp_path,NOW+timedelta(hours=4))
    assert any(f['code']=='missed_cycle' for f in later['findings'])
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    (tmp_path/'data/advisor/run_status.json').write_text('{"ok":false}')
    assert any(f['code']=='failed_cycle' for f in watchdog.inspect(tmp_path,NOW)['findings'])


def test_recovery_restores_same_hash_and_cash_and_rejects_tampering(tmp_path):
    root=tmp_path/'source';root.mkdir();l=archive(root)
    z=tmp_path/'backup.zip';recovery.backup(root,z)
    assert recovery.drill(z)['ledger_hash']==l.root_hash
    result=recovery.restore(z,tmp_path/'restored')
    assert result['accounts']['strategy']==l.account()
    with pytest.raises(ValueError):recovery.restore(z,tmp_path/'restored')
    with zipfile.ZipFile(z) as original:
        contents={name:original.read(name) for name in original.namelist()}
    contents['data/advisor/events.jsonl']+=b'\n'
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as out:
        for name,data in contents.items():out.writestr(name,data)
    with pytest.raises(ValueError,match='checksum'):recovery.drill(bad)


def test_watchdog_night_run_cannot_hide_missing_daytime_session(tmp_path):
    archive(tmp_path)
    p=tmp_path/'data/advisor/latest.json';s=json.loads(p.read_text())
    night=NOW.replace(hour=20);s['generated_at']=night.isoformat();p.write_text(json.dumps(s))
    result=watchdog.inspect(tmp_path,night)
    assert any(f['code']=='missed_cycle' for f in result['findings'])


def test_watchdog_observes_a_daytime_gap_without_blocking_the_producer(tmp_path):
    archive(tmp_path)
    early = watchdog.inspect(tmp_path, NOW + timedelta(minutes=25))
    assert not any(f['code'] == 'cycle_gap' for f in early['findings'])
    late = watchdog.inspect(tmp_path, NOW + timedelta(minutes=55))
    assert any(f['code'] == 'cycle_gap' for f in late['findings'])
    after_close = watchdog.inspect(tmp_path, NOW + timedelta(hours=4))
    assert any(f['code'] == 'cycle_gap' for f in after_close['findings'])


@pytest.mark.parametrize('daytime_check', [False, True])
def test_closing_valuation_cannot_substitute_for_execution_window(tmp_path, daytime_check):
    ledger = archive(tmp_path)
    day = '2026-09-17'
    config_path = tmp_path / 'advisor/config.json'
    cfg = json.loads(config_path.read_text())
    cfg.update(execution_window={'open': '10:15', 'close': '18:00'},
               observation_window={'open': '10:15', 'close': '20:00'})
    config_path.write_text(json.dumps(cfg))
    close = datetime.fromisoformat(day + 'T19:32:00+03:00')
    evening = close + timedelta(hours=2)
    fields = dict(valid_quotes=1, expected_quotes=1, decisions=1, in_observation_window=True)
    if daytime_check:
        ledger.add('session_check', 'real-session', day + 'T11:20:00+03:00',
                   in_execution_window=True, **fields)
    ledger.add('session_check', 'valuation-only', close.isoformat(),
               in_execution_window=False, **fields)
    ledger.save()
    findings = watchdog.inspect(tmp_path, evening)['findings']
    assert any(f['code'] == 'no_execution_cycle' for f in findings) == (not daytime_check)
