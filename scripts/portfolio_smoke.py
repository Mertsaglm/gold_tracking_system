"""Gerçek SQL arşivinin geçici kopyasında iki kotasyonlu, ağsız tam çevrim."""
from __future__ import annotations

import hashlib
import argparse
import json
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from advisor import history, service, universe
from advisor.calendar import IST
from advisor.ledger import Ledger, atomic_json
from scripts.audit_production import audit_ledgers


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def next_weekday(day):
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def run(archive_override=None, output_override=None):
    cfg = service.configuration(ROOT)
    market = cfg['market']
    archive = Path(archive_override) if archive_override else ROOT / 'data' / ('bist.sql' if market == 'bist' else 'altin.sql')
    if output_override:
        destination = Path(output_override).resolve()
        if destination == archive.resolve() or destination.is_relative_to((ROOT/'data').resolve()):
            raise ValueError('Prova makbuzu kaynak arşive veya gerçek veri dizinine yazılamaz.')
    source_hash = sha(archive)
    with history.connection(ROOT, market, dump_path=archive) as con:
        table = 'bars_daily' if market == 'bist' else 'history_daily'
        asof = con.execute('SELECT max(date) FROM ' + table).fetchone()[0]
        if market == 'bist':
            names = sorted(universe.members(universe.read(ROOT), next_weekday(date.fromisoformat(asof)).isoformat()))
            marks = {symbol: con.execute('SELECT c FROM bars_daily WHERE ticker=? AND date=?',
                                         (symbol, asof)).fetchone() for symbol in names}
            marks = {s: float(row[0]) for s, row in marks.items() if row and row[0] and row[0] > 0}
            missing = sorted(set(names) - set(marks))
        else:
            marks = {'GRAM': float(con.execute('SELECT gram_teorik FROM history_daily WHERE date=?',
                                               (asof,)).fetchone()[0])}
            missing = []
    day = next_weekday(date.fromisoformat(asof))
    now = datetime(day.year, day.month, day.day, 13, 30, tzinfo=IST).astimezone(timezone.utc)
    with tempfile.TemporaryDirectory(prefix='portfolio-smoke-') as directory:
        work = Path(directory)
        (work/'advisor').mkdir()
        (work/'data').mkdir()
        cfg['start_date'] = day.isoformat()
        cfg['experiment_start_date'] = day.isoformat()
        cfg['account_id'] = 'portfolio-smoke'
        cfg['telegram']['enabled'] = False
        atomic_json(work/'advisor/config.json', cfg)
        for name in ('universe-history.json',):
            if (ROOT/'advisor'/name).exists():
                shutil.copy2(ROOT/'advisor'/name, work/'advisor'/name)
        shutil.copy2(ROOT/'holidays_tr.yaml', work/'holidays_tr.yaml')
        shutil.copy2(archive, work/'data'/archive.name)

        def quotes(stamp):
            return {s: {'symbol': s, 'bid': price, 'ask': price,
                        'reference_price': price, 'quoted_at': stamp.isoformat(),
                        'observed_at': stamp.isoformat(), 'kind': 'historical_assumption',
                        'source': 'arşiv kapanışı; test varsayımı'}
                    for s, price in marks.items()}

        first = service.cycle(work, now=now, quotes=quotes(now), offline=True)
        later = now + timedelta(minutes=30)
        second = service.cycle(work, now=later, quotes=quotes(later), offline=True)
        state = work/'data/advisor/accounts/portfolio-smoke'
        ledger_paths = [state/'events.jsonl', *(state/'portfolio_candidates').glob('*/events.jsonl')]
        money_kinds = {'contribution','fill','corporate_action','dividend_receivable',
                       'dividend_payment','account_fee'}
        def financial_events():
            return {str(p.relative_to(state)):
                    [(e['kind'], e['key'], e['data']) for e in Ledger(p).events if e['kind'] in money_kinds]
                    for p in ledger_paths}
        before_replay = financial_events()
        service.cycle(work, now=later, quotes=quotes(later), offline=True)
        after_replay = financial_events()
        if before_replay != after_replay:
            changed = [name for name in before_replay if before_replay[name] != after_replay[name]]
            raise AssertionError('Aynı kotasyon mali hareket ekledi: ' + ','.join(changed))
        backup = work/'backup'
        shutil.copytree(state, backup)
        restored = {str(p.relative_to(backup)): Ledger(p).root_hash
                    for p in backup.rglob('events.jsonl')}
        original = {str(p.relative_to(state)): Ledger(p).root_hash
                    for p in state.rglob('events.jsonl')}
        if restored != original or sha(archive) != source_hash:
            raise AssertionError('Yedek eşliği veya kaynak arşivi değişmezliği bozuldu.')
        # Ledger.account dışında ayrı olay indirgemesiyle nakit, lot, alacak ve ücret denetlenir.
        independently_checked = audit_ledgers(work)
        expected_ledgers = {str(path.relative_to(work)) for path in ledger_paths}
        if not expected_ledgers <= set(independently_checked):
            raise AssertionError('Bağımsız muhasebe bütün aday defterlerini kapsamadı.')
        experiments = second.get('portfolio_experiments', {})
        if len(experiments.get('accounts', [])) != 5:
            raise AssertionError('Beş adayın tamamı oluşmadı: ' + json.dumps(experiments, ensure_ascii=False)[:500])
        report = {'market': market, 'source_asof': asof, 'simulation_day': day.isoformat(),
                  'source_archive_sha256': source_hash, 'quotes': len(marks),
                  'missing_archive_quotes': missing,
                  'first_status': first['portfolio_experiments']['status'],
                  'candidate_count': len(experiments['accounts']),
                  'core_cash_positions': len(next(a for a in experiments['accounts'] if a['id']=='core-cash')['strategy']['positions']),
                  'idempotent': True, 'backup_restored': True,
                  'independent_accounting': True, 'audited_ledgers': len(expected_ledgers),
                  'historical_quote_assumption': True, 'live_price_claim': False,
                  'comparison_aligned': experiments['comparison']['aligned'],
                  'health_errors': second['health']['errors']}
    output = Path(output_override) if output_override else ROOT/'reports'/f'portfolio-smoke-{market}-{asof}.json'
    atomic_json(output, report)
    print(json.dumps({'output': str(output), **report}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Salt okunur başka bir SQL dökümü')
    parser.add_argument('--output', type=Path, help='Makbuzun yazılacağı yol')
    args = parser.parse_args()
    run(args.archive, args.output)
