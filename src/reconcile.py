"""Kapalı seans beklentisini yalnız onu izleyen ilk açık günle karşılaştırır.

Eski reconciled bayrağı kanıt değildir: 2026-09-22 denetiminde farklı haftalar
29 Temmuz'un aynı gerçekleşmesiyle kapatılmıştı. Eşleşme ham tarihlerden türetilir.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import math

from . import db, util
from .market_calendar import MarketCalendar

log = logging.getLogger('reconcile')


def comparisons(con, cfg, now=None):
    """Salt okunur doğrulama; doğru günün verisi yoksa sonraki haftaya sıçrama."""
    now = now or util.utcnow()
    cal = MarketCalendar(cfg)
    valid = {}
    for r in con.execute('SELECT ts_utc,prim_pct FROM prim_history WHERE indicative=0 AND weekend=0 ORDER BY ts_utc'):
        stamp = datetime.fromisoformat(r['ts_utc'])
        value = r['prim_pct']
        if stamp.tzinfo is None or stamp > now or value is None or not math.isfinite(value):
            continue
        if not cal.is_forex_open(stamp) or cal.is_tr_holiday(stamp) or cal.is_us_gold_holiday(stamp):
            continue
        day = util.to_local(stamp, cal.tz_off).date()
        valid.setdefault(day, r)
    items = []
    for r in con.execute('SELECT * FROM weekend_expectation ORDER BY ts_utc'):
        stamp = datetime.fromisoformat(r['ts_utc'])
        if stamp.tzinfo is None or stamp > now:
            continue
        day = util.to_local(stamp, cal.tz_off).date()
        for offset in range(15):
            candidate = day + timedelta(days=offset)
            noon = datetime(candidate.year, candidate.month, candidate.day, 9, tzinfo=timezone.utc)
            if noon > stamp and cal.is_forex_open(noon) and not cal.is_tr_holiday(noon) and not cal.is_us_gold_holiday(noon):
                break
        else:
            candidate = None
        match = valid.get(candidate)
        if match and datetime.fromisoformat(match['ts_utc']) <= stamp:
            match = None
        actual = match['prim_pct'] if match else None
        items.append({'ts': r['ts_utc'], 'expected_day': candidate.isoformat() if candidate else None,
                      'realized_at': match['ts_utc'] if match else None,
                      'beklenti_pct': r['expectation_pct'], 'gerceklesen_pct': actual,
                      'fark_puan': actual-r['expectation_pct'] if actual is not None and r['expectation_pct'] is not None else None,
                      'recorded_reconciled': bool(r['reconciled']), 'valid': match is not None})
    return items


def reconcile(cfg: dict) -> dict:
    con = db.connect(cfg)
    try:
        rows = comparisons(con, cfg)
        corrected = sum(r['recorded_reconciled'] != r['valid'] for r in rows)
        for r in rows:
            con.execute('UPDATE weekend_expectation SET reconciled=? WHERE ts_utc=?', (int(r['valid']), r['ts']))
        con.commit()
        items = [r for r in rows if r['valid'] and not r['recorded_reconciled']]
        pending = sum(not r['valid'] for r in rows)
        log.info('mutabakat: %d yeni eşleşme, %d veri bekliyor, %d işaret düzeltildi', len(items), pending, corrected)
        return {'reconciled': len(items), 'pending': pending, 'corrected_flags': corrected, 'items': items}
    finally:
        con.close()


if __name__ == '__main__':
    util.load_env()
    print(reconcile(util.load_config()))
