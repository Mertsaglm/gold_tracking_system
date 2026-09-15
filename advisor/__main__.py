from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import history, review, service
from .ledger import atomic_json


def main():
    p = argparse.ArgumentParser(description="BIST/altın sanal yatırım sistemi")
    p.add_argument("command", choices=["cycle", "audit", "research", "status", 'notify'])
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    p.add_argument("--database", type=Path)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--notify", action="store_true")
    p.add_argument("--telegram", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    cfg = service.configuration(args.root)
    if args.command == 'research':
        from .research import retrospective
        with history.connection(args.root, cfg['market'], args.database) as con:
            result = retrospective(con, cfg)
        out = args.output or args.root / 'reports/karar-sonuclari-2026-09-15.json'
        atomic_json(out, result)
        print(json.dumps(result, ensure_ascii=False))
    elif args.command == "audit":
        with history.connection(args.root, cfg["market"], args.database) as con:
            value = review.audit(args.root, con, cfg["market"], args.telegram)
        out = args.output or args.root / "reports/revizyon-denetimi.json"
        atomic_json(out, value)
        print(json.dumps({"report": str(out), "files": len(value["files"]), "tables": len(value["tables"]), "integrity": value["integrity"]}))
    elif args.command == 'notify':
        from .notifications import publish
        from .ledger import Ledger, locked
        with locked(args.root / 'data/advisor/.lock'):
            ledger = Ledger(args.root / 'data/advisor/events.jsonl')
            snapshot = json.loads((args.root / 'data/advisor/latest.json').read_text())
            sent = publish(args.root, cfg, snapshot, ledger, datetime.now(timezone.utc))
            print(json.dumps({'telegram_sent': sent}))
    elif args.command == "status":
        from .notifications import summary
        print(summary(json.loads((args.root / "data/advisor/latest.json").read_text())))
    else:
        try:
            value = service.cycle(args.root, database=args.database, offline=args.offline, notify=args.notify)
        except Exception as exc:
            # Sağlayıcı URL'si API anahtarı taşıyabilir; hata metni/traceback yayımlama.
            error = {'at': datetime.now(timezone.utc).isoformat(), 'ok': False, 'error_type': type(exc).__name__}
            atomic_json(args.root / 'data/advisor/run_status.json', error)
            latest = args.root / 'data/advisor/latest.json'
            if latest.exists():
                old = json.loads(latest.read_text())
                old['health']['errors'] = ['Son koşu tamamlanamadı: ' + type(exc).__name__]
                old['health']['last_attempt'] = error['at']
                atomic_json(latest, old)
            print(json.dumps(error))
            raise SystemExit(1) from None
        atomic_json(args.root / 'data/advisor/run_status.json', {'at': value['generated_at'], 'ok': not value['health']['errors']})
        print(json.dumps({"market": value["market"], "analysis_date": value["analysis_date"], "decisions": len(value["decisions"]), "errors": value["health"]["errors"]}, ensure_ascii=False))
        if value['health']['errors'] and not args.offline:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
