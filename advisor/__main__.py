from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import history, review, service
from .ledger import atomic_json
from .accounts import state_path


def main():
    p = argparse.ArgumentParser(description="BIST/altın sanal yatırım sistemi")
    p.add_argument("command", choices=["cycle", "audit", "research", "status", 'notify', 'watchdog', 'backup', 'recovery-check',
                                     'simulate', 'experiment', 'compare-methods', 'train-models', 'reproduce', 'settle-dividends', 'cost-observations', 'universe-import', 'weekly'])
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    p.add_argument("--database", type=Path)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--notify", action="store_true")
    p.add_argument('--closing-refresh', action='store_true', help='BIST kapanış verisi gecikse de yalnız değerleme yap; işlem üretme.')
    p.add_argument("--telegram", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument('--input', type=Path)
    p.add_argument('--start')
    p.add_argument('--end')
    p.add_argument('--scenario', type=Path)
    args = p.parse_args()
    cfg = service.configuration(args.root)
    state = state_path(args.root, cfg)
    if args.command == 'train-models':
        from . import training, research, universe
        if not args.end or not args.output:p.error('train-models için --end ve --output gerekli.')
        if args.output.resolve().is_relative_to((args.root/'data').resolve()):p.error('Eğitim paketi gerçek veri/defter dizinine yazılamaz.')
        with history.connection(args.root,cfg['market'],args.database) as con:
            frame=history.load(con,cfg['market'],args.end)
            if cfg.get('watchlist_enabled'):
                watched=universe.members(universe.read(args.root),cfg['start_date'])
                frame['in_live']=frame.symbol.isin(watched).astype(int)
                frame.attrs['live_symbols']=sorted(watched)
            result=training.bundle(frame,cfg,args.end,research.decision_rows(con,cfg))
        atomic_json(args.output,result)
        print(json.dumps({'report':str(args.output),'data_through':result['contract']['data_through'],
                          'trained':sum('weights' in r['model'] for r in result['models']), 'activated':False}))
    elif args.command in ('simulate', 'experiment', 'compare-methods'):
        from .simulation import simulate
        from .universe import read
        from .calendar import load
        if not args.start or not args.end or not args.output:p.error('simulate için --start, --end ve --output gerekli.')
        if args.output.resolve().is_relative_to((args.root/'data').resolve()):p.error('Simülasyon raporu gerçek veri dizinine yazılamaz.')
        cfg['calendar']=load(args.root)
        with history.connection(args.root,cfg['market'],args.database) as con:
            frame=history.load(con,cfg['market'],args.end)
            regimes=None
            if args.command=='compare-methods' and cfg['market']=='bist':
                from .comparisons import v1_history
                from datetime import date,timedelta
                regimes=v1_history(con,(date.fromisoformat(args.start)-timedelta(days=30)).isoformat(),args.end)
        scenario=json.loads(args.scenario.read_text()) if args.scenario else {}
        if args.command in ('experiment','compare-methods'):
            from .experiments import compare
            if cfg.get('watchlist_enabled'):
                from .universe import members
                watched=members(read(args.root),cfg['start_date'])
                frame['in_live']=frame.symbol.isin(watched).astype(int)
                frame.attrs['live_symbols']=sorted(watched)
            if args.command=='compare-methods':
                from .comparisons import compare as compare_methods
                if scenario:p.error('compare-methods sabit sözleşmedir; --scenario kullanılamaz.')
                result=compare_methods(frame,cfg,args.start,args.end,regimes)
            else:
                result=compare(frame,cfg,args.start,args.end,scenario=scenario)
        else:
            result=simulate(frame,cfg,args.start,args.end,membership=read(args.root),scenario=scenario)
        atomic_json(args.output,result)
        print(json.dumps({'report':str(args.output),'production_eligible':False}))
    elif args.command == 'reproduce':
        from .capsule import reproduce
        if not args.input:p.error('reproduce için --input gerekli.')
        print(json.dumps(reproduce(args.input)))
    elif args.command == 'universe-import':
        from .universe import import_history
        if not args.input:p.error('universe-import için --input gerekli.')
        print(json.dumps(import_history(args.root,args.input)))
    elif args.command in ('settle-dividends','cost-observations'):
        from .ledger import Ledger,locked
        from .corporate import settle
        from .observations import record
        if not args.input:p.error('Doğrulanmış kayıtları içeren --input gerekli.')
        with locked(state / '.lock'):
            ledger=Ledger(state / 'events.jsonl')
            count=(settle if args.command=='settle-dividends' else record)(ledger,json.loads(args.input.read_text()),datetime.now(timezone.utc))
            ledger.save()
        print(json.dumps({'added':count,'note':'Panel bir sonraki cycle ile güncellenir.'}))
    elif args.command == 'weekly':
        from .ledger import Ledger,locked
        from .reporting import weekly,weekly_text
        with locked(state / '.lock'):
            ledger=Ledger(state / 'events.jsonl')
            now=datetime.now(timezone.utc)
            snapshot={'market':cfg['market'],'weekly':weekly(ledger,now)}
            print(weekly_text(snapshot))
            if args.notify:
                from .notifications import publish_weekly
                publish_weekly(cfg,snapshot,ledger,now)
    elif args.command == 'watchdog':
        from .watchdog import inspect
        value = inspect(args.root, datetime.now(timezone.utc))
        print(json.dumps(value, ensure_ascii=False))
        raise SystemExit(0 if value['ok'] else 1)
    elif args.command in ('backup', 'recovery-check'):
        from .recovery import backup, drill
        if args.command == 'backup':
            if not args.output:
                p.error('backup için --output gerekli.')
            value = backup(args.root, args.output)
        else:
            if not args.input:
                p.error('recovery-check için --input gerekli.')
            value = drill(args.input)
        print(json.dumps(value, ensure_ascii=False))
    elif args.command == 'research':
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
        with locked(state / '.lock'):
            ledger = Ledger(state / 'events.jsonl')
            snapshot = json.loads((state / 'latest.json').read_text())
            sent = publish(args.root, cfg, snapshot, ledger, datetime.now(timezone.utc))
            print(json.dumps({'telegram_sent': sent}))
    elif args.command == "status":
        from .notifications import summary
        if not (state / 'latest.json').exists():
            print('Yeni sanal hesabın ilk uygun koşusu bekleniyor; eski hesap arşivi korunuyor.')
            return
        print(summary(json.loads((state / 'latest.json').read_text())))
    else:
        try:
            value = service.cycle(args.root, database=args.database, offline=args.offline, notify=args.notify, closing_refresh=args.closing_refresh)
        except Exception as exc:
            # Sağlayıcı URL'si API anahtarı taşıyabilir; hata metni/traceback yayımlama.
            error = {'at': datetime.now(timezone.utc).isoformat(), 'ok': False, 'error_type': type(exc).__name__}
            atomic_json(state / 'run_status.json', error)
            atomic_json(args.root / 'data/advisor/run_status.json', error)
            for latest in {state / 'latest.json', args.root / 'data/advisor/latest.json'}:
                if latest.exists():
                    old = json.loads(latest.read_text())
                    old['health']['errors'] = ['Son koşu tamamlanamadı: ' + type(exc).__name__]
                    old['health']['last_attempt'] = error['at']
                    atomic_json(latest, old)
            print(json.dumps(error))
            raise SystemExit(1) from None
        status = {'at': value['generated_at'], 'ok': not value['health']['errors'], 'skipped': value.get('skipped', False)}
        atomic_json(state / 'run_status.json', status)
        atomic_json(args.root / 'data/advisor/run_status.json', status)
        if value.get('skipped'):
            print(json.dumps({"market": value["market"], "skipped": True, "reason": value['skip_reason']}, ensure_ascii=False))
            return
        print(json.dumps({"market": value["market"], "analysis_date": value["analysis_date"], "decisions": len(value["decisions"]), "errors": value["health"]["errors"]}, ensure_ascii=False))
        if value['health']['errors'] and not args.offline:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
