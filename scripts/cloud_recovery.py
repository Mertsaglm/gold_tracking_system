"""GitHub'da eksik çevrimi veya raporu denetler; yazma işini ilgili workflow yürütür."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from advisor import calendar


def daily_slot(now, cfg):
    bist = cfg['market'] == 'bist'
    cutoff = (20, 50) if bist else (19, 50)
    if (now.hour, now.minute) >= cutoff:
        day = now.date()
    elif now.hour < 4:
        day = now.date() - timedelta(days=1)
    else:
        return None
    calendar.require_coverage(day.isoformat(), day.isoformat(), cfg)
    if bist and not calendar.trading_day(day, cfg):
        return None
    return now.replace(year=day.year, month=day.month, day=day.day,
                       hour=cutoff[0], minute=cutoff[1], second=0, microsecond=0)


def missing_cycle(now, cfg, status):
    day = now.date()
    calendar.require_coverage(day.isoformat(), day.isoformat(), cfg)
    opening, closing = calendar.window(day, cfg, 'observation')
    if not calendar.trading_day(day, cfg) or not opening <= now < closing:
        return None
    interval = timedelta(minutes=60 if cfg['market'] == 'bist' else 45)
    slot = opening + ((now - opening) // interval) * interval
    if now < opening + timedelta(minutes=15):
        return None
    if status and status.get('ok') is True and status.get('skipped') is False:
        at = datetime.fromisoformat(status['at'])
        if max(opening, now - interval) <= at <= now:
            return None
    return slot


def recently_requested(runs, now, slot):
    for run in runs:
        at = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
        if run['status'] != 'completed' or at >= now - timedelta(minutes=10):
            return True
        if (at >= slot and run['event'] == 'workflow_dispatch'
                and run['actor']['login'] == 'github-actions[bot]'):
            return True
    return False


def api(path, *, raw=False, missing_ok=False, payload=None):
    headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
               'Accept': 'application/vnd.github.raw+json' if raw else 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    data = None if payload is None else json.dumps(payload).encode()
    request = Request('https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + '/' + path,
                      headers=headers, data=data)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
    except HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise
    return json.loads(body) if body else None


def dispatch(workflow, slot, now, inputs=None):
    path = 'actions/workflows/' + workflow
    runs = api(path + '/runs?branch=main&per_page=100')['workflow_runs']
    if recently_requested(runs, now, slot):
        print(workflow, 'bekleyen, yeni veya aynı aralık için telafi koşusu var')
        return
    api(path + '/dispatches', payload={'ref': 'main', 'inputs': inputs or {}})
    print(workflow, 'telafi istendi', slot.isoformat())


def main():
    root = Path.cwd()
    cfg = json.loads((root / 'advisor/config.json').read_text())
    cfg['calendar'] = calendar.load(root)
    now = datetime.now(calendar.IST)
    bist = cfg['market'] == 'bist'
    slot = daily_slot(now, cfg)
    if slot:
        name = 'gunluk' if bist else 'rapor'
        report = f'reports/{name}_{slot.date()}.md'
        if api('contents/' + report + '?ref=main', missing_ok=True) is None:
            dispatch('gunluk.yml' if bist else 'daily.yml', slot, now)
            return
    if missing_cycle(now, cfg, None):
        account = cfg['account_id']
        status = api(f'contents/data/advisor/accounts/{account}/run_status.json?ref=main',
                     raw=True, missing_ok=True)
        slot = missing_cycle(now, cfg, status)
        if slot:
            dispatch('portfolio.yml', slot, now, {'manual_run': 'true'} if bist else {})
            return
    print('Telafi gerekmiyor.')


if __name__ == '__main__':
    main()
