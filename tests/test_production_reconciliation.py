"""2026-09-22 üretim logu: 398 hafta sonu kaydı tek eski prime bağlanıyordu."""
from datetime import datetime, timezone

from src import db, reconcile, signals, util


def test_reconciliation_uses_first_valid_price_of_the_correct_day(izole_kok, monkeypatch):
    cfg, root = izole_kok
    monkeypatch.setattr(util, 'utcnow', lambda: datetime(2026,9,22,12,tzinfo=timezone.utc))
    con = db.connect(cfg)
    for ts, value in [('2026-09-11T10:00:00+00:00', -9), ('2026-09-14T09:00:00+00:00', 1),
                      ('2026-09-14T12:00:00+00:00', 2), ('2026-09-28T09:00:00+00:00', 99)]:
        con.execute('INSERT INTO prim_history(ts_utc,prim_pct,indicative,weekend) VALUES(?,?,0,0)',(ts,value))
    a, b = '2026-09-12T10:00:00+00:00', '2026-09-19T10:00:00+00:00'
    for ts in (a,b): db.insert_weekend_exp(con,ts,100,100,.5)
    con.execute('UPDATE weekend_expectation SET reconciled=1 WHERE ts_utc=?',(b,))
    con.commit();con.close()
    result = reconcile.reconcile(cfg)
    assert result['reconciled'] == 1 and result['pending'] == 1
    assert result['items'][0]['gerceklesen_pct'] == 1
    assert result['items'][0]['realized_at'] == '2026-09-14T09:00:00+00:00'
    assert reconcile.reconcile(cfg)['reconciled'] == 0
    con = db.connect(cfg)
    assert con.execute('SELECT reconciled FROM weekend_expectation WHERE ts_utc=?',(b,)).fetchone()[0] == 0
    db.insert_weekend_exp(con,a,100,100,.5)
    assert con.execute('SELECT reconciled FROM weekend_expectation WHERE ts_utc=?',(a,)).fetchone()[0] == 1
    db.insert_weekend_exp(con,a,101,100,1.5)
    assert con.execute('SELECT reconciled FROM weekend_expectation WHERE ts_utc=?',(a,)).fetchone()[0] == 0
    con.close()


def test_missing_regime_keeps_other_signals_and_discloses_missing_data(izole_kok, monkeypatch):
    cfg, root = izole_kok
    from src import indicators
    monkeypatch.setattr(signals, '_current_regime', lambda *a: (None,None))
    monkeypatch.setattr(indicators, 'build_panel', lambda *a: {'signals':[], 'consensus':{'yon':'notr','score':0,'n':0,'normalized':0}})
    result = signals.build_signals(cfg)
    assert next(s for s in result['signals'] if s['sinyal']=='rejim')['yon'] == 'veri_bekliyor'
    assert any(s['sinyal']=='prim_zskoru' for s in result['signals'])


def test_weekend_report_uses_the_same_matching_and_honest_denominator(izole_kok, monkeypatch):
    from src import report
    cfg, _ = izole_kok
    monkeypatch.setattr(util,'utcnow',lambda:datetime(2026,9,22,12,tzinfo=timezone.utc))
    con=db.connect(cfg)
    con.execute("INSERT INTO prim_history(ts_utc,prim_pct,indicative,weekend) VALUES('2026-09-14T09:00:00+00:00',7,0,0)")
    for hour,value in [(13,1),(14,3),(15,None)]:
        db.insert_weekend_exp(con,f'2026-09-19T{hour}:00:00+00:00',100,100,value)
    text='\n'.join(report.weekend_section(con,cfg))
    assert '%+2.00' in text and '2/3' in text
    assert 'bekleniyor' in text and '2026-09-21' in text
    assert '%+7.00' not in text
    con.execute("INSERT INTO prim_history(ts_utc,prim_pct,indicative,weekend) VALUES('2026-09-21T09:00:00+00:00',2.5,0,0)")
    text='\n'.join(report.weekend_section(con,cfg))
    assert '%+2.50' in text and '+0.50 puan' in text
    assert '2/3' in text
    con.close()
