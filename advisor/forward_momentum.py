"""Bağımsız ileri BIST momentum portföyü ve eş bütçeli pasif kıyas."""
from datetime import datetime
import math

from . import benchmark, corporate, costs, marketdata, policy, portfolio_candidates as portfolio
from .calendar import IST
from .ledger import Ledger, fund
from .service import benchmark_nav, feedback


def cycle(state, cfg, records, rows, quotes, now, actions):
    start = cfg.get('forward_momentum_start')
    day = now.astimezone(IST).date().isoformat()
    if cfg['market'] != 'bist' or not start or day < start:
        return None
    ledger = Ledger(state / 'forward_momentum' / 'events.jsonl')
    members = portfolio.core_members(records, day, 'bist')
    scores = {symbol: ((100 + row['momentum120']) / (100 + row['momentum20']) - 1) * 100
              for symbol, row in rows.items() if symbol in members and row.get('quality_ok')
              and row['date'] == cfg['expected_analysis_date'] and row.get('momentum120') is not None
              and math.isfinite(row['momentum120']) and row.get('momentum20') is not None
              and math.isfinite(row['momentum20']) and row['momentum20'] > -100
              and row.get('volatility20') is not None and math.isfinite(row['volatility20'])}
    covered = len(members) == 30 and len(scores) == 30
    phase = cfg['execution_phase']
    if not ledger.events and (phase != 'entry' or not covered or not any(
            marketdata.usable(quotes.get(symbol), cfg, now) is None for symbol in members)):
        return {'status': 'İlk geçerli giriş gözlemi bekleniyor', 'rank_coverage': len(scores)}
    at = now.isoformat()
    contract = next((event['data'] for event in ledger.events if event['kind'] == 'forward_contract'), None)
    terms = {'policy_id': 'bist-momentum-120-20-v1', 'start_date': day,
             'initial_try': cfg['initial_try'], 'monthly_try': cfg['monthly_try']}
    if contract:
        terms['start_date'] = contract['start_date']
        if terms != contract:
            raise ValueError('İleri momentum hesabı bütçesi mühürlü.')
    ledger.add('forward_contract', 'forward-contract', at, **terms)
    cfg = {**cfg, 'start_date': terms['start_date']}
    cfg['blocked_symbols'] = {**cfg['blocked_symbols'], **corporate.reconcile(ledger, actions, cfg, now)}
    fund(ledger, cfg, day, at)
    ranking = sorted(scores, key=lambda s: (-scores[s], s))
    rank = {symbol: i for i, symbol in enumerate(ranking, 1)}
    week = 'forward-review:' + portfolio._week(day)
    review = covered and phase == 'entry' and week not in ledger.keys
    pending = []
    for symbol, position in ledger.account()['positions'].items():
        quote = quotes.get(symbol)
        if phase not in ('entry', 'protection') or marketdata.usable(quote, cfg, now, allow_wide_spread=True):
            if review and rank.get(symbol, 99) > 10:
                pending.append('satış kotasyonu eksik')
            continue
        sell = policy.execution_price(quote, cfg, 'SELL')
        hit = position.get('stop') and sell <= position['stop']
        if hit or (review and rank.get(symbol, 99) > 10):
            trade = portfolio._trade(ledger, cfg, quotes, now, 'strategy', symbol, 'SELL',
                                     float(position['quantity']) * sell, reason='momentum_stop' if hit else 'momentum_rank_exit')
            if trade['status'] != 'doldu':
                pending.append(trade['status'])
    if review:
        account = ledger.account()
        view = policy.value_account(account, quotes, cfg, now)
        exited = {f['symbol'] for f in account['fills'] if f['side'] == 'SELL'
                  and datetime.fromisoformat(f['at']).astimezone(IST).date().isoformat() == day}
        slots = 5 - len(account['positions'])
        if view['valuation_complete'] and slots > 0:
            eligible = [s for s in ranking[:5] if s not in account['positions'] and s not in exited]
            for symbol in eligible[:slots]:
                quote = quotes.get(symbol)
                if marketdata.usable(quote, cfg, now):
                    pending.append('alış kotasyonu eksik')
                    continue
                buy = policy.execution_price(quote, cfg, 'BUY')
                stop = buy * (1 - max(.02, rows[symbol]['volatility20'] * .025))
                budget = portfolio._risk_limited_budget(ledger.account(), symbol, cfg, buy, stop,
                                                        view['equity_try'] * .08, view['equity_try'] * .006)
                if budget > 0:
                    trade = portfolio._trade(ledger, cfg, quotes, now, 'strategy', symbol, 'BUY', budget,
                                             stop=stop, reason='momentum_top5')
                    if trade['status'] not in ('doldu', 'lot_yetersiz'):
                        pending.append(trade['status'])
        elif not view['valuation_complete']:
            pending.append('değerleme eksik')
        if not pending:
            ledger.add('forward_review', week, at, ranking=ranking)
    benchmark.step(ledger, cfg, quotes, members, now)
    costs.accrue(ledger, cfg, quotes, now)
    strategy = policy.value_account(ledger.account(), quotes, cfg, now)
    passive = policy.value_account(ledger.account('benchmark'), quotes, cfg, now)
    performance = feedback(ledger, strategy)
    passive_nav = benchmark_nav(ledger, passive)
    if strategy['valuation_complete']:
        ledger.add('valuation', 'valuation:' + at, at, equity_try=strategy['equity_try'],
                   contributed_try=strategy['contributed_try'], nav=performance['nav'],
                   benchmark_try=passive['equity_try'], benchmark_nav=passive_nav)
    ledger.save()
    return {'status': 'İleri sanal deney', 'start_date': terms['start_date'], 'rank_coverage': len(scores),
            'strategy': strategy, 'benchmark': passive, 'feedback': performance, 'benchmark_nav': passive_nav,
            'pending': pending,
            'ledger_hash': ledger.root_hash}
