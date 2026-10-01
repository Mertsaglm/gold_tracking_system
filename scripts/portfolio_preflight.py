"""İki piyasanın ortak T0 öncesi salt-okunur hazır olma kontrolü."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from advisor import history, portfolio_candidates, service, universe
from advisor.calendar import IST, load as load_calendar, trading_day


def start_issues(start, today, cfg):
    if not start:
        return ['İleri deney için T0 tarihi açık değil.']
    try:
        launch = date.fromisoformat(start)
    except (TypeError, ValueError):
        return ['T0 geçerli YYYY-MM-DD tarihi değil.']
    issues = []
    if launch <= today:
        issues.append('T0 geçmişe veya bugüne ayarlanamaz; ortak gelecek işlem günü olmalı.')
    if not trading_day(launch, cfg):
        issues.append('T0 bir işlem günü değil.')
    calendar = cfg.get('calendar', {})
    if not calendar.get('available') or str(launch.year) not in calendar.get('years', []):
        issues.append('T0 yılı için doğrulanmış işlem takvimi yok.')
    return issues


def inspect(root):
    cfg = service.configuration(root)
    today = datetime.now(IST).date()
    previous = today - timedelta(days=1)
    cfg['calendar'] = load_calendar(root)
    while not trading_day(previous, cfg):
        previous -= timedelta(days=1)
    with history.connection(root, cfg['market']) as con:
        table = 'bars_daily' if cfg['market'] == 'bist' else 'history_daily'
        latest = con.execute('SELECT max(date) FROM ' + table).fetchone()[0]
        missing = []
        if cfg['market'] == 'bist':
            members = portfolio_candidates.core_members(universe.read(root), today.isoformat(), 'bist')
            for symbol in sorted(members):
                row = con.execute('SELECT c,v FROM bars_daily WHERE ticker=? AND date=?',
                                  (symbol, latest)).fetchone()
                if not row or not row[0] or row[0] <= 0 or not row[1] or row[1] <= 0:
                    missing.append(symbol)
        else:
            members = {'GRAM'}
            row = con.execute('SELECT gram_teorik,ons_usd,usdtry FROM history_daily WHERE date=?',
                              (latest,)).fetchone()
            if not row or any(value is None or value <= 0 for value in row):
                missing.append('GRAM')
    reasons = start_issues(cfg.get('experiment_start_date'), today, cfg)
    if latest < previous.isoformat():
        reasons.append(f'Kapanış eski: {latest}; beklenen en az {previous.isoformat()}')
    if cfg['market'] == 'bist' and len(members) != 30:
        reasons.append(f'Tarihli BIST30 üyeliği {len(members)}; beklenen 30')
    if missing:
        reasons.append('Son kaynak gününde eksik/geçersiz: ' + ', '.join(missing))
    return {'market':cfg['market'], 'latest_archive_date':latest,
            'expected_previous_session':previous.isoformat(), 'core_members':len(members),
            'missing':missing, 'start_date':cfg.get('experiment_start_date'),
            'initial_try':cfg['initial_try'], 'monthly_try':cfg['monthly_try'],
            'ready':not reasons, 'reasons':reasons}


def main():
    if '--single' in sys.argv:
        print(json.dumps(inspect(ROOT), ensure_ascii=False))
        return 0
    peer = ROOT.parent / ('gold_tracking_system' if ROOT.name != 'gold_tracking_system' else 'BIST tahmin')
    from scripts import advisor_manifest
    try:
        advisor_manifest.check(ROOT, peer)
        advisor_manifest.check(peer, ROOT)
        code_ok = True
    except ValueError:
        code_ok = False
    peer_result = subprocess.run([str(peer/'.venv/bin/python'), str(peer/'scripts/portfolio_preflight.py'), '--single'],
                                 cwd=peer, check=True, capture_output=True, text=True, timeout=60)
    markets = [inspect(ROOT), json.loads(peer_result.stdout)]
    by_market = {m['market']:m for m in markets}
    dates = {m['start_date'] for m in markets}
    budgets = {(m['initial_try'],m['monthly_try']) for m in markets}
    reasons = []
    if not code_ok: reasons.append('Ortak Python motorları eşit değil.')
    if len(dates) != 1 or None in dates: reasons.append('İki piyasada aynı açık T0 tarihi yok.')
    if budgets != {(50000,5000)}: reasons.append('İki piyasanın 50.000/5.000 TL bütçesi eşit değil.')
    local_ready = code_ok and all(m['ready'] for m in markets) and not reasons
    result = {'ready':local_ready, 'scope':'yerel arşiv ve ortak T0 kontrolü',
              'markets':by_market,'reasons':reasons,
              'external_scheduler_verified':False,
              'production_ready':False,
              'note':'Yerel ready=true bile canlı banka kotasyonu, dış scheduler veya üretim sürüm eşliği değildir.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
