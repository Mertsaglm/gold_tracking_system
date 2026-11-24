"""Karar defterinden maliyetli BEKLE sonuçlarını üretir."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import mean, median

from . import calendar, filter_diagnostics, marketdata, policy
from .ledger import cents


def net_return(entry, exit_quote, cfg, budget):
    buy = Decimal(str(policy.execution_price(entry, cfg, 'BUY')))
    sell = Decimal(str(policy.execution_price(exit_quote, cfg, 'SELL')))
    quantity = policy.quantity_for(budget, float(buy), cfg)
    if not quantity:
        return None
    cost = cents(quantity * buy) + policy.fee(cfg, quantity * buy, 'BUY')
    proceeds = cents(quantity * sell) - policy.fee(cfg, quantity * sell, 'SELL')
    return (proceeds - cost) / budget * 100


def measure(ledger, cfg, *, start, through, budget, corporate_days):
    decisions = []
    signals = {}
    prices = defaultdict(list)
    spreads = defaultdict(list)
    navs = {}
    fills = Counter()
    entry_days = set()
    last_strategy_buy = None
    start, through = date.fromisoformat(start), date.fromisoformat(through)
    calendar.require_coverage(start.isoformat(), through.isoformat(), cfg)
    latest = None
    for event in ledger.events:
        if event['kind'] not in ('decision', 'quote_snapshot', 'valuation', 'fill'):
            continue
        at = datetime.fromisoformat(event['at']).astimezone(calendar.IST)
        day = at.date()
        if not start <= day <= through:
            continue
        latest = max(latest, at) if latest else at
        data = event['data']
        phase = calendar.phase(at, cfg)
        if event['kind'] == 'fill':
            fills[(data['book'], data['side'])] += 1
            if data['book'] == 'strategy' and data['side'] == 'BUY':
                last_strategy_buy = max(day, last_strategy_buy or day)
        elif event['kind'] == 'valuation':
            navs[at] = data.get('benchmark_nav')
        elif event['kind'] == 'quote_snapshot' and phase in ('entry', 'protection', 'valuation'):
            for symbol, quote in data['quotes'].items():
                if marketdata.price_problem(quote, cfg, at) is not None:
                    continue
                if cfg['market'] == 'gold' and symbol == 'GRAM':
                    spread = (quote['ask'] / quote['bid'] - 1) * 100
                    spreads[f'{at.hour:02d}:00'].append(spread)
                if phase != 'valuation' and quote.get('tradable') is not False:
                    prices[(day, symbol)].append((at, quote, phase))
        elif event['kind'] == 'decision' and phase == 'entry':
            decisions.append(data)
            entry_days.add(day)
            prediction = data.get('prediction') or {}
            horizon = prediction.get('horizon_sessions', data.get('horizon_sessions', 20))
            if (data['action'] == 'BEKLE' and prediction.get('raw_pct', data.get('forecast_pct')) is not None
                    and data.get('asof') and type(horizon) is int and horizon > 0):
                key = (day, data['symbol'], data['asof'], horizon)
                previous = signals.get(key)
                if previous is None or at < previous[0]:
                    signals[key] = (at, event)
    results = []
    for (day, symbol, asof, horizon), (at, event) in sorted(signals.items()):
        maturity = calendar.add_sessions(day, horizon, cfg)
        outcome = {'decision_key': event['key'], 'symbol': symbol, 'asof': asof, 'decision_at': at.isoformat(),
                   'code': event['data']['code'], 'maturity': maturity, 'horizon_sessions': horizon}
        maturity_day = date.fromisoformat(maturity)
        if (cfg.get('calendar') is not None and
                str(maturity_day.year) not in cfg['calendar']['years']):
            outcome.update(status='pending_calendar', maturity=None)
        elif maturity_day > latest.date():
            outcome['status'] = 'pending'
        elif any(day <= action <= maturity_day for action in corporate_days.get(symbol, ())):
            outcome['status'] = 'corporate_action'
        else:
            settle(outcome, at, prices[(day, symbol)], prices[(maturity_day, symbol)], navs, cfg, budget)
        results.append(outcome)
    diagnostics = filter_diagnostics.summarize(decisions)
    inactivity_days = (latest.date() - (last_strategy_buy or start)).days if latest else None
    return {
        'market': cfg['market'], 'through_observation': latest.isoformat() if latest else None,
        'ledger_hash': ledger.root_hash, 'start': start.isoformat(), 'through': through.isoformat(),
        'fills': [{'book': book, 'side': side, 'count': n} for (book, side), n in sorted(fills.items())],
        'entry_days_observed': len(entry_days),
        'entry_days_expected': sum(calendar.trading_day(start + timedelta(days=offset), cfg)
                                   for offset in range(((latest.date() - start).days + 1) if latest else 0)),
        'strategy_days_without_new_buy': inactivity_days,
        'strategy_inactivity_review': inactivity_days is not None and inactivity_days >= 60,
        'entry_diagnostics': diagnostics,
        'outcomes_by_code': summarize_outcomes(results),
        'gold_spread_by_hour': {hour: {'n': len(values), 'min_pct': min(values), 'median_pct': median(values),
                                      'max_pct': max(values), 'over_cap': sum(x > cfg['max_spread_pct'] for x in values)}
                                for hour, values in sorted(spreads.items())},
        'budget_try': budget / 100, 'outcomes': results,
    }


def settle(outcome, at, entries, exits, navs, cfg, budget):
    entries = sorted(entries, key=lambda row: row[0])
    quote_before = next((q for observed, q, _ in reversed(entries) if observed <= at), None)
    next_quote = None
    if quote_before and marketdata.price_problem(quote_before, cfg, at) is None:
        stamp = datetime.fromisoformat(quote_before['quoted_at'])
        expiry = at + timedelta(minutes=cfg.get('entry_intent_minutes', 90))
        next_quote = next((row for row in entries if at < row[0] <= expiry and row[2] == 'entry'
                           and datetime.fromisoformat(row[1]['quoted_at']) > stamp), None)
    if next_quote is None:
        outcome['status'] = 'no_entry_quote'
        return
    if not exits:
        outcome['status'] = 'no_maturity_quote'
        return
    entry_at, entry, _ = next_quote
    exit_at, exit_quote, _ = min(exits, key=lambda row: row[0])
    net = net_return(entry, exit_quote, cfg, budget)
    if net is None:
        outcome['status'] = 'lot_unaffordable'
        return
    first_nav, last_nav = navs.get(entry_at), navs.get(exit_at)
    passive_pct = (last_nav / first_nav - 1) * 100 if first_nav and last_nav is not None else None
    outcome.update(status='measured', entry_at=entry_at.isoformat(), exit_at=exit_at.isoformat(),
                   net_pct=net, passive_pct=passive_pct,
                   excess_pct=net - passive_pct if passive_pct is not None else None)


def summarize_outcomes(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['code']].append(row)
    summary = {}
    for code, group in sorted(groups.items()):
        matured = [row for row in group if row['status'] == 'measured']
        net = [row['net_pct'] for row in matured]
        excess = [row['excess_pct'] for row in matured if row['excess_pct'] is not None]
        cohorts = {}
        for row in matured:
            signal_day = row['decision_at'][:10]
            cohorts[signal_day] = max(row['maturity'], cohorts.get(signal_day, ''))
        periods, previous_end = 0, ''
        for signal_day, maturity in sorted(cohorts.items()):
            if signal_day > previous_end:
                periods += 1
                previous_end = maturity
        summary[code] = {
            'statuses': dict(Counter(row['status'] for row in group)),
            'measured_signal_days': len(cohorts), 'non_overlapping_periods': periods,
            'beat_cash': sum(value > 0 for value in net), 'mean_net_pct': mean(net) if net else None,
            'passive_comparable': len(excess), 'beat_passive': sum(value > 0 for value in excess),
            'mean_excess_pct': mean(excess) if excess else None,
        }
    return summary
