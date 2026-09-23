"""Önceki kapanış yetişmediğinde V2 veri arşivinin atomik onarımı."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src import advisor_refresh, db, dbdump, history, util


NOW = datetime(2026, 9, 23, 7, tzinfo=timezone.utc)


def seed(tmp_path):
    root = tmp_path
    (root / 'data').mkdir()
    original = Path(__file__).resolve().parents[1]
    for name in ('config.yaml', 'holidays_tr.yaml'):
        (root / name).write_bytes((original / name).read_bytes())
    cfg = util.load_config(root / 'config.yaml')
    cfg['paths']['db'] = str(root / 'seed.sqlite')
    con = db.connect(cfg)
    code = cfg['sources']['evds']['series']['usdtry_sell']
    con.executemany('INSERT INTO evds_daily(date,series_code,value) VALUES(?,?,?)',
                    [('2026-09-21', code, 48.7), ('2026-09-22', code, 48.8)])
    con.execute("INSERT INTO history_daily(date,ons_usd,usdtry,gram_teorik,ons_source) "
                "VALUES('2026-09-21',4000,48.7,6270,'GC=F')")
    con.commit(); con.close()
    dbdump.dump(cfg, str(root / 'data/altin.sql'))
    return root


def test_refresh_adds_only_closed_bar_and_is_idempotent(tmp_path, monkeypatch):
    root = seed(tmp_path)
    monkeypatch.setattr(util, 'utcnow', lambda: NOW)
    called = []
    def ons(cfg, start, min_days):
        called.append((cfg['sources']['yfinance']['ons_hist_primary'],
                       cfg['sources']['yfinance']['ons_ticker']))
        return {'2026-09-21': 4000, '2026-09-22': 4010, '2026-09-23': 4020}, 'GC=F'
    monkeypatch.setattr(history, '_yf_ons_daily', ons)
    out = advisor_refresh.refresh(root, NOW)
    assert out['status'] == 'updated' and out['last'] == '2026-09-22'
    assert called == [('GC=F', 'GC=F')]
    source = root / 'data/altin.sql'
    after = source.read_bytes()
    assert b"2026-09-23', 4020" not in after  # yarım gün barı dışarıda
    assert advisor_refresh.refresh(root, NOW)['status'] == 'already_current'
    assert source.read_bytes() == after


def test_refresh_failure_leaves_original_dump_byte_identical(tmp_path, monkeypatch):
    root = seed(tmp_path)
    monkeypatch.setattr(util, 'utcnow', lambda: NOW)
    monkeypatch.setattr(history, '_yf_ons_daily', lambda *a, **k: ({'2026-09-21': 4000}, 'GC=F'))
    source = root / 'data/altin.sql'; before = source.read_bytes()
    with pytest.raises(ValueError, match='Beklenen altın kapanışı'):
        advisor_refresh.refresh(root, NOW)
    assert source.read_bytes() == before


def test_future_dated_row_cannot_hide_missing_expected_close(tmp_path, monkeypatch):
    root = seed(tmp_path)
    source = root / 'data/altin.sql'
    with source.open('a') as out:
        out.write("\nINSERT INTO history_daily(date,ons_usd,usdtry,gram_teorik,ons_source) "
                  "VALUES('2026-09-24',4030,48.8,6320,'GC=F');\n")
    before = source.read_bytes()
    monkeypatch.setattr(util, 'utcnow', lambda: NOW)
    monkeypatch.setattr(history, '_yf_ons_daily', lambda *a, **k: ({'2026-09-21': 4000}, 'GC=F'))
    with pytest.raises(ValueError, match='Beklenen altın kapanışı'):
        advisor_refresh.refresh(root, NOW)
    assert source.read_bytes() == before
