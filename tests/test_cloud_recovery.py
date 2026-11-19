from datetime import datetime
import json
from pathlib import Path

from advisor import calendar
from scripts import cloud_recovery as recovery


def config(market):
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / 'advisor/config.json').read_text())
    cfg.update(market=market, calendar=calendar.load(root))
    cfg['observation_window'] = {'open': '09:00', 'close': '23:30', 'half_day_close': '23:30'}
    return cfg


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=calendar.IST)


def test_daily_cutoff_previous_day_and_weekend():
    bist, gold = config('bist'), config('gold')
    assert recovery.daily_slot(at('2026-11-18T20:49'), bist) is None
    assert recovery.daily_slot(at('2026-11-18T21:00'), bist) == at('2026-11-18T20:50')
    assert recovery.daily_slot(at('2026-11-19T02:00'), gold) == at('2026-11-18T19:50')
    assert recovery.daily_slot(at('2026-11-21T21:00'), bist) is None


def test_gold_evening_gap_and_following_fresh_receipt():
    cfg = config('gold')
    stale = {'ok': True, 'skipped': False, 'at': '2026-11-18T15:38:21+00:00'}
    assert recovery.missing_cycle(at('2026-11-18T21:36'), cfg, stale)
    fresh = dict(stale, at='2026-11-18T18:41:40+00:00')
    assert recovery.missing_cycle(at('2026-11-18T21:50'), cfg, fresh) is None
    assert recovery.missing_cycle(at('2026-11-18T21:50'), cfg, dict(fresh, skipped=True))
    assert recovery.missing_cycle(at('2026-11-18T23:49'), cfg, stale) is None


def test_recovery_dispatch_and_duplicates(monkeypatch):
    now, slot = at('2026-11-18T21:36'), at('2026-11-18T20:50')
    prior = []
    writes = []

    def api(path, *, payload=None):
        if payload is not None:
            writes.append((path, payload))
        return {'workflow_runs': prior}

    monkeypatch.setattr(recovery, 'api', api)
    recovery.dispatch('gunluk.yml', slot, now)
    assert writes == [('actions/workflows/gunluk.yml/dispatches', {'ref': 'main', 'inputs': {}})]
    run = dict(created_at='2026-11-18T18:00:00Z', status='completed',
               event='workflow_dispatch', actor={'login': 'github-actions[bot]'})
    prior.append(run)
    recovery.dispatch('gunluk.yml', slot, now)
    assert len(writes) == 1
    assert recovery.recently_requested([dict(run, event='schedule', status='queued')], now, slot)
    assert recovery.recently_requested([dict(run, event='schedule', created_at='2026-11-18T18:34:00Z')], now, slot)


def test_failed_recovery_can_be_retried_once_after_cooldown():
    now, slot = at('2026-11-18T21:36'), at('2026-11-18T20:50')
    failed = dict(created_at='2026-11-18T18:00:00Z', status='completed', conclusion='failure',
                  event='workflow_dispatch', actor={'login': 'github-actions[bot]'})
    second = dict(failed, created_at='2026-11-18T18:15:00Z', conclusion='timed_out')
    assert not recovery.recently_requested([failed], now, slot)
    assert recovery.recently_requested([second, failed], now, slot)
    assert recovery.recently_requested([dict(failed, created_at='2026-11-18T18:30:00Z')], now, slot)


def test_missing_report_has_priority_over_portfolio(monkeypatch, tmp_path):
    import shutil
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'advisor').mkdir()
    (tmp_path / 'advisor/config.json').write_text(json.dumps(config('gold')))
    shutil.copyfile(root / 'holidays_tr.yaml', tmp_path / 'holidays_tr.yaml')
    monkeypatch.chdir(tmp_path)

    class Evening(datetime):
        @classmethod
        def now(cls, tz):
            return at('2026-11-18T21:36')

    writes = []

    def mock_api(path, *, missing_ok=False, payload=None):
        if path.startswith('contents/reports/'):
            assert missing_ok and 'rapor_2026-11-18.md' in path
            return None
        if path.endswith('/dispatches'):
            writes.append(path)
        else:
            assert 'daily.yml/runs' in path
        return {'workflow_runs': []}

    monkeypatch.setattr(recovery, 'datetime', Evening)
    monkeypatch.setattr(recovery, 'api', mock_api)
    recovery.main()
    assert writes == ['actions/workflows/daily.yml/dispatches']
