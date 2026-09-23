"""V2 öncesi son kapanışı geçici DB'de doğrula; yalnız tam sonuçta dump'ı değiştir."""
from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from advisor.calendar import IST, load, trading_day

from . import db, dbdump, evds_job, history, util
from .sources import evds


def refresh(root: Path = util.ROOT, now: datetime | None = None) -> dict:
    root = Path(root).resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Saat dilimi eksik.')
    expected = now.astimezone(IST).date() - timedelta(days=1)
    calendar = {'calendar': load(root)}
    while not trading_day(expected, calendar):
        expected -= timedelta(days=1)
    expected_day = expected.isoformat()
    source = root / 'data/altin.sql'
    if not source.is_file():
        raise FileNotFoundError('Altın SQL arşivi eksik.')
    with tempfile.TemporaryDirectory(prefix='advisor-gold-refresh-') as temp:
        cfg = copy.deepcopy(util.load_config(root / 'config.yaml'))
        cfg['paths']['db'] = str(Path(temp) / 'altin.sqlite')
        dbdump.restore(cfg, str(source))
        con = db.connect(cfg)
        try:
            ready = con.execute('SELECT date FROM history_daily WHERE date=?', (expected_day,)).fetchone()
            if ready:
                return {'status': 'already_current', 'expected': expected_day, 'last': expected_day}
            latest = con.execute('SELECT date,ons_source FROM history_daily WHERE date<? ORDER BY date DESC LIMIT 1',
                                 (expected_day,)).fetchone()
            usd_code = cfg['sources']['evds']['series']['usdtry_sell']
            usd = con.execute('SELECT value FROM evds_daily WHERE date=? AND series_code=?',
                              (expected_day, usd_code)).fetchone()
            if usd is None or usd['value'] is None:
                start = (expected - timedelta(days=7)).strftime('%d-%m-%Y')
                rows = evds.fetch_series(cfg, usd_code, start=start)
                evds_job._upsert(con, usd_code, rows)
                con.commit()
            # Canlı geçmiş GC=F ise tek barlık kaynak değişimi yapma.
            # Kaynak göçü ayrı bir ölçüm ve karar gerektirir.
            if latest and latest['ons_source']:
                cfg['sources']['yfinance']['ons_hist_primary'] = latest['ons_source']
                cfg['sources']['yfinance']['ons_ticker'] = latest['ons_source']
        finally:
            con.close()
        result = history.update_recent(cfg)
        con = db.connect(cfg)
        try:
            last = con.execute('SELECT date,ons_source FROM history_daily WHERE date=?', (expected_day,)).fetchone()
            last_day = last['date'] if last else None
            if last_day is None:
                raise ValueError('Beklenen altın kapanışı henüz alınamadı: ' + expected_day)
            if latest and latest['ons_source'] and last['ons_source'] != latest['ons_source']:
                raise ValueError('Ons kaynak sürekliliği bozuldu.')
        finally:
            con.close()
        staged = Path(temp) / 'altin.sql'
        dbdump.dump(cfg, str(staged))
        # /tmp ile checkout ayrı filesystem olabilir; rename hedef dizinde atomiktir.
        with tempfile.NamedTemporaryFile(dir=source.parent, prefix='.advisor-refresh-',
                                         suffix='.sql', delete=False) as target:
            pending = Path(target.name)
            try:
                with staged.open('rb') as handle:
                    shutil.copyfileobj(handle, target)
                target.flush()
                os.fsync(target.fileno())
            except BaseException:
                pending.unlink(missing_ok=True)
                raise
        try:
            os.replace(pending, source)
        finally:
            pending.unlink(missing_ok=True)
        return {'status': 'updated', 'expected': expected_day, 'last': last_day,
                'ons_source': result.get('ons_source')}


def main() -> int:
    try:
        print(json.dumps(refresh(), ensure_ascii=False))
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({'status': 'unavailable', 'reason': str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
