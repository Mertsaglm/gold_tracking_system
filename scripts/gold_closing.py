"""Planlı altın kapanışının gecikmesinde yalnız gün sonu Telegram makbuzu yaz."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

from advisor import calendar, notifications
from advisor.accounts import state_path
from advisor.ledger import Ledger, locked
from advisor.service import configuration


def run(root, now, *, primary):
    cfg = configuration(root)
    cfg['calendar'] = calendar.load(root)
    local = now.astimezone(calendar.IST)
    today = local.date()
    opening, observation_end = calendar.window(today, cfg, 'observation')
    if primary and calendar.phase(local, cfg) == 'valuation':
        return {'run_cycle': True, 'sent': False}

    if local < opening:
        day = today - timedelta(days=1)
    elif local > observation_end:
        day = today
    else:
        return {'run_cycle': False, 'sent': False}
    calendar.require_coverage(day.isoformat(), day.isoformat(), cfg)
    if day.isoformat() < cfg['start_date'] or not calendar.trading_day(day, cfg):
        return {'run_cycle': False, 'sent': False}

    state = state_path(root, cfg)
    with locked(state / '.lock'):
        ledger = Ledger(state / 'events.jsonl')
        latest = state / 'latest.json'
        snapshot = json.loads(latest.read_text()) if latest.is_file() else None
        sent = notifications.recover_closing(cfg, ledger, now, day.isoformat(), snapshot)
    return {'run_cycle': False, 'sent': sent, 'report_day': day.isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary', action='store_true')
    args = parser.parse_args()
    result = run(Path.cwd(), datetime.now(calendar.IST), primary=args.primary)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
