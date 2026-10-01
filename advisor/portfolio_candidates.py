"""Ön kayıtlı çekirdek/taktik sanal hesaplar; ana defterden bağımsızdır."""
from __future__ import annotations

import copy
import json
import math
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

from . import corporate, costs, engine, marketdata, policy, universe
from .calendar import IST
from .ledger import Ledger, atomic_json, cents, digest

POLICY_ID = 'core-tactical-80-20-v1'
CATALOG = ('legacy-control', 'core-cash', 'core-passive', 'core-ridge', 'core-specialized')


def _week(day):
    iso = datetime.fromisoformat(day).isocalendar()
    return f'{iso.year}-W{iso.week:02d}'


def _completed(actions):
    """Engelli emir varken haftalık kontrol tamamlandı sayılmaz."""
    return all(action['status'] in ('doldu', 'tekrar') for action in actions)


def owned(state):
    symbols = set()
    for spec in CATALOG:
        path = Path(state) / 'portfolio_candidates' / spec / 'events.jsonl'
        if path.exists():
            ledger = Ledger(path)
            for book in (('strategy',) if spec == 'legacy-control' else ('core', 'tactical')):
                symbols.update(ledger.account(book)['positions'])
    return symbols


def core_members(records, day, market):
    if market == 'gold':
        return {'GRAM'}
    active = universe.members(records, day)
    latest = {}
    for row in sorted(records, key=lambda r: (r['known_at'], r['effective_from'])):
        if (row['known_at'] <= day and row['effective_from'] <= day and
                (not row.get('effective_to') or day < row['effective_to'])):
            latest[row['symbol']] = row
    return {symbol for symbol in active if 'BIST30' in latest[symbol].get('reason', '')}


def _fund(ledger, cfg, day, now, spec):
    from datetime import date
    start = date.fromisoformat(cfg['start_date'])
    if date.fromisoformat(day) < start:
        return
    books = ('strategy',) if spec == 'legacy-control' else ('core', 'tactical')
    year, month = start.year, start.month
    periods = [(start.isoformat(), cfg['initial_try'], 'initial')]
    while True:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        if (year, month) > (int(day[:4]), int(day[5:7])):
            break
        periods.append((f'{year:04d}-{month:02d}', cfg['monthly_try'], 'monthly'))
    for period, total, kind in periods:
        amount = cents(total)
        shares = {'strategy': amount} if spec == 'legacy-control' else {'core': amount * 80 // 100, 'tactical': amount - amount * 80 // 100}
        for book in books:
            ledger.add('contribution', f'{book}:{kind}:{period}', now.isoformat(),
                       book=book, amount_cents=shares[book], period=period)


def _view(ledger, cfg, quotes, now, spec):
    books = ('strategy',) if spec == 'legacy-control' else ('core', 'tactical')
    parts = {book: policy.value_account(ledger.account(book), quotes, cfg, now) for book in books}
    complete = all(part['valuation_complete'] for part in parts.values())
    equity = sum(part['equity_try'] for part in parts.values()) if complete else None
    contributed = sum(part['contributed_try'] for part in parts.values())
    return {'equity_try': equity, 'contributed_try': contributed,
            'pnl_try': equity - contributed if equity is not None else None,
            'cash_try': sum(part['cash_try'] for part in parts.values()),
            'realized_try': sum(part['realized_try'] for part in parts.values()),
            'receivable_try': sum(part['receivable_try'] for part in parts.values()),
            'fee_liability_try': sum(part['fee_liability_try'] for part in parts.values()),
            'valuation_complete': complete, 'parts': parts,
            'positions': [{**position, 'sleeve': book} for book, part in parts.items() for position in part['positions']],
            'fills': [fill for part in parts.values() for fill in part['fills']],
            'account_fees_try': sum(part['account_fees_try'] for part in parts.values())}


def _size(delta_try, price, cfg, held=None):
    step = Decimal('1') if cfg['market'] == 'bist' else Decimal('0.01')
    if delta_try <= 0:
        return Decimal(0)
    quantity = (Decimal(str(delta_try / price)) / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if held is not None:
        quantity = min(quantity, Decimal(str(held)))
    return quantity


def _trade(ledger, cfg, quotes, now, book, symbol, side, target_delta_try, *, stop=None, sector=None, reason='target_weight'):
    if cfg.get('execution_phase') == 'valuation' or (side == 'BUY' and cfg.get('execution_phase') != 'entry'):
        return {'status': 'işlem_saati_kapalı', 'symbol': symbol, 'book': book}
    q = quotes.get(symbol)
    problem = cfg.get('blocked_symbols', {}).get(symbol) or marketdata.usable(
        q, cfg, now, cfg.get('holidays', ()), allow_wide_spread=side == 'SELL')
    if problem:
        return {'status': 'veri_engeli', 'symbol': symbol, 'book': book, 'reason': problem}
    if side == 'BUY' and book == 'tactical':
        day = now.astimezone(IST).date().isoformat()
        if any(f['symbol'] == symbol and f['side'] == 'SELL' and
               datetime.fromisoformat(f['at']).astimezone(IST).date().isoformat() == day
               for f in ledger.account(book)['fills']):
            return {'status': 'aynı_gün_satış', 'symbol': symbol, 'book': book}
    if side == 'BUY' and not marketdata.entry_ready(ledger, cfg, q, symbol, now, book):
        return {'status': 'sonraki_kotasyon', 'symbol': symbol, 'book': book}
    account = ledger.account(book)
    price = policy.execution_price(q, cfg, side)
    if side == 'BUY':
        budget_cents = min(account['cash_cents'], cents(target_delta_try))
        qty = policy.quantity_for(budget_cents, price, cfg)
    else:
        held = account['positions'].get(symbol)
        if not held:
            return {'status': 'pozisyon_yok', 'symbol': symbol, 'book': book}
        qty = min(held['quantity'], _size(target_delta_try, price, cfg, held['quantity']))
        if target_delta_try >= float(held['quantity']) * price - price * (1 if cfg['market'] == 'bist' else .01) / 2:
            qty = held['quantity']
    if qty <= 0:
        return {'status': 'lot_yetersiz', 'symbol': symbol, 'book': book}
    # Lot × fiyat kuruşa yuvarlanmadan önce Decimal kalmalı; float yarım kuruşta sapar.
    notional = qty * Decimal(str(price))
    fee = policy.fee(cfg, float(notional), side)
    day = now.astimezone(IST).date().isoformat()
    quote_id = digest({'quoted_at': q['quoted_at'], 'source': q.get('source')})
    key = f'{book}:{day}:{symbol}:{side}:{quote_id}'
    added = ledger.add('fill', key, now.isoformat(), book=book, symbol=symbol, side=side,
                       quantity=str(qty), price=price, notional_cents=cents(notional), fee_cents=fee,
                       quote=q, reason=reason, decision_key=key, policy_id=POLICY_ID,
                       stop=stop, target=None, deadline=None, sector=sector)
    if added:
        ledger.account(book)  # Negatif nakit ve hayalet satış diske yazılmadan reddedilir.
    return {'status': 'doldu' if added else 'tekrar', 'symbol': symbol, 'book': book,
            'side': side, 'quantity': str(qty), 'fee_try': fee / 100}


def _valid(row, symbol, cfg, quotes, now):
    if not row or not row.get('quality_ok') or row.get('date') != cfg.get('expected_analysis_date'):
        return False
    return not cfg.get('blocked_symbols', {}).get(symbol) and marketdata.usable(
        quotes.get(symbol), cfg, now, cfg.get('holidays', ())) is None


def _core(ledger, cfg, records, rows, quotes, now, book='core'):
    actions = []
    if cfg.get('execution_phase') not in ('entry', 'protection'):
        return actions
    day = now.astimezone(IST).date().isoformat()
    members = core_members(records, day, cfg['market'])
    if cfg['market'] == 'bist' and len(members) != cfg.get('core_expected_members', 30):
        return [{'status': 'çekirdek_üyeliği_eksik', 'observed': len(members),
                 'expected': cfg.get('core_expected_members', 30)}]
    account = ledger.account(book)
    if cfg['market'] == 'gold':
        if cfg.get('execution_phase') != 'entry':
            return actions
        symbols = members
        # Pasif altın kontrolünün taktik dilimi de GRAM alır.
        for symbol in symbols:
            if _valid(rows.get(symbol), symbol, cfg, quotes, now):
                budget = account['cash_cents'] / 100
                if budget > 0:
                    actions.append(_trade(ledger, cfg, quotes, now, book, symbol, 'BUY', budget,
                                          reason='core_accumulation'))
        return actions
    # Bir önceki haftanın dengelemesi aynı hafta ikinci defa satış üretmez.
    week = _week(day)
    rebalance = f'core-rebalance:{book}:{week}' not in ledger.keys
    usable_members = [symbol for symbol in sorted(members) if _valid(rows.get(symbol), symbol, cfg, quotes, now)]
    for symbol in sorted(set(account['positions']) - members):
        p = account['positions'][symbol]
        q = quotes.get(symbol)
        if q:
            actions.append(_trade(ledger, cfg, quotes, now, book, symbol, 'SELL',
                                  float(p['quantity']) * policy.execution_price(q, cfg, 'SELL'),
                                  reason='index_exit'))
    if cfg.get('execution_phase') != 'entry':
        return actions
    if not usable_members:
        return actions + [{'status': 'çekirdek_verisi_yok'}]
    view = policy.value_account(ledger.account(book), quotes, cfg, now)
    if not view['valuation_complete']:
        return actions + [{'status': 'eksik_değerleme'}]
    target = view['equity_try'] / len(members)
    current = {p['symbol']: p['value_try'] for p in view['positions']}
    deficits = {s: max(0, target - (current.get(s) or 0)) for s in usable_members}
    # Önce mevcut nakit eksik ağırlıklara gider; satış yalnız bant aşıldığında.
    if rebalance and sum(deficits.values()) > view['cash_try']:
        for symbol in sorted(set(account['positions']) & members):
            value = current.get(symbol)
            if value is not None and value > target * 1.25:
                actions.append(_trade(ledger, cfg, quotes, now, book, symbol, 'SELL', value - target,
                                      reason='core_band_rebalance'))
    for symbol in sorted(usable_members, key=lambda s: (-deficits[s], s)):
        if deficits[symbol] > 0:
            actions.append(_trade(ledger, cfg, quotes, now, book, symbol, 'BUY', deficits[symbol],
                                  sector=rows[symbol].get('sector'), reason='core_accumulation'))
    if rebalance and len(usable_members) == len(members) and _completed(actions):
        ledger.add('rebalance_check', f'core-rebalance:{book}:{week}', now.isoformat(),
                   book=book, target_weight=1 / len(members), members=sorted(members))
    return actions


def _net_forecast(row, forecast, quote, cfg, notional_try=1000):
    if forecast is None or not quote or not isinstance(row.get('close'), (int, float)):
        return None
    reference = quote.get('reference_price') if cfg['market'] == 'gold' else quote.get('bid')
    if not reference or reference <= 0 or not math.isfinite(row['close']):
        return None
    remaining = (row['close'] * (1 + forecast / 100) / reference - 1) * 100
    buy = policy.execution_price(quote, cfg, 'BUY')
    sell = policy.execution_price(quote, cfg, 'SELL')
    cost = (buy / sell - 1) * 100 + (policy.fee(cfg, notional_try, 'BUY') +
                                      policy.fee(cfg, notional_try, 'SELL')) / notional_try
    return remaining - cost


def _risk_limited_budget(account, symbol, cfg, buy, stop, desired_try, risk_limit_try):
    """Gerçek lot ve iki yön masrafıyla yeni stop zararını sınırla."""
    quantity = policy.quantity_for(cents(min(desired_try, account['cash_cents'] / 100)), buy, cfg)
    held = account['positions'].get(symbol)
    old_qty = held['quantity'] if held else Decimal(0)
    old_cost = held['cost_cents'] if held else 0
    step = Decimal('1') if cfg['market'] == 'bist' else Decimal('.01')
    while quantity > 0:
        total_qty = old_qty + quantity
        entry_try = float(quantity) * buy
        exit_try = float(total_qty) * stop
        loss = max(0, old_cost + cents(entry_try) + policy.fee(cfg, entry_try, 'BUY')
                   - cents(exit_try) + policy.fee(cfg, exit_try, 'SELL')) / 100
        if loss <= risk_limit_try + .0001:
            return (cents(entry_try) + policy.fee(cfg, entry_try, 'BUY')) / 100
        quantity -= step
    return 0


def _tactical(ledger, cfg, rows, quotes, forecasts, scores, now):
    account = ledger.account('tactical')
    actions = []
    # Koruyucu stop haftalık seçimin dışında, gözlem boyunca işler.
    for symbol, p in list(account['positions'].items()):
        q = quotes.get(symbol)
        if q and p.get('stop') and marketdata.usable(q, cfg, now, cfg.get('holidays', ()), allow_wide_spread=True) is None:
            price = policy.execution_price(q, cfg, 'SELL')
            if price <= p['stop']:
                actions.append(_trade(ledger, cfg, quotes, now, 'tactical', symbol, 'SELL',
                                      float(p['quantity']) * price, reason='tactical_stop'))
    account = ledger.account('tactical')
    exited_today = {f['symbol'] for f in account['fills'] if f['side'] == 'SELL' and
                    datetime.fromisoformat(f['at']).astimezone(IST).date() == now.astimezone(IST).date()}
    day = now.astimezone(IST).date().isoformat()
    week = _week(day)
    key = 'tactical-rebalance:' + week
    if key in ledger.keys or cfg.get('execution_phase') != 'entry':
        return actions
    if cfg['market'] == 'gold':
        symbol = 'GRAM'
        if not _valid(rows.get(symbol), symbol, cfg, quotes, now):
            return actions
        net = _net_forecast(rows[symbol], forecasts.get(symbol), quotes[symbol], cfg)
        if net is None:
            return actions
        proposal = {'symbol': symbol, 'net_forecast_pct': net, 'target_value_try': None,
                    'stop': None, 'reason': '1pct_entry_0pct_exit'}
        held_now = account['positions'].get(symbol)
        if held_now:
            proposal['target_value_try'] = float(held_now['quantity']) * policy.execution_price(quotes[symbol], cfg, 'SELL')
            proposal['stop'] = held_now.get('stop')
        if net >= 1:
            view = _view(ledger, cfg, quotes, now, 'core-ridge')
            if view['equity_try'] is not None:
                held = account['positions'].get(symbol)
                current = float(held['quantity']) * policy.execution_price(quotes[symbol], cfg, 'SELL') if held else 0
                cap = min(account['cash_cents'] / 100 + current, view['equity_try'] * .20)
                if cap > current:
                    buy = policy.execution_price(quotes[symbol], cfg, 'BUY')
                    stop = buy * (1 - max(.02, float(rows[symbol].get('volatility20') or 0) * .025))
                    delta = _risk_limited_budget(account, symbol, cfg, buy, stop,
                                                 cap - current, view['equity_try'] * .01)
                    proposal.update(target_value_try=current + delta, stop=stop)
                    if delta > 0 and _net_forecast(rows[symbol], forecasts[symbol], quotes[symbol], cfg, delta) >= 1:
                        actions.append(_trade(ledger, cfg, quotes, now, 'tactical', symbol, 'BUY', delta,
                                              stop=stop, reason='gold_tactical_entry'))
        elif net <= 0 and symbol in account['positions']:
            proposal['target_value_try'] = 0
            held = account['positions'][symbol]
            actions.append(_trade(ledger, cfg, quotes, now, 'tactical', symbol, 'SELL',
                                  float(held['quantity']) * policy.execution_price(quotes[symbol], cfg, 'SELL'),
                                  reason='gold_tactical_exit'))
        if _completed(actions):
            ledger.add('rebalance_check', key, now.isoformat(), book='tactical',
                       net_forecast_pct=net, proposals=[proposal])
        return actions
    valid = {s: r for s, r in rows.items() if s in cfg['allowed_entry_symbols'] and _valid(r, s, cfg, quotes, now)}
    if not valid:
        return actions
    ordered = sorted(valid, key=lambda s: (-(scores.get(s, float('-inf'))), s))
    rank = {s: i + 1 for i, s in enumerate(ordered)}
    net = {s: _net_forecast(r, forecasts.get(s), quotes[s], cfg) for s, r in valid.items()}
    held = set(account['positions'])
    keep = {s for s in held if s not in exited_today and rank.get(s, 999) <= 10
            and net.get(s) is not None and net[s] > 0}
    sector_counts = {}
    for s in keep:
        sector = valid[s].get('sector')
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    for symbol in ordered[:5]:
        if len(keep) >= 5:
            break
        if symbol in keep or symbol in exited_today or net[symbol] is None or net[symbol] < 1 or scores.get(symbol, 0) <= 0:
            continue
        sector = valid[symbol].get('sector')
        if sector_counts.get(sector, 0) >= 2:
            continue
        keep.add(symbol)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    for symbol in sorted(held - keep):
        q = quotes.get(symbol)
        if q:
            actions.append(_trade(ledger, cfg, quotes, now, 'tactical', symbol, 'SELL',
                                  float(account['positions'][symbol]['quantity']) * policy.execution_price(q, cfg, 'SELL'),
                                  reason='tactical_rank_exit'))
    view = _view(ledger, cfg, quotes, now, 'core-ridge')
    proposals = []
    if view['equity_try'] is not None:
        equity = view['equity_try']
        for symbol in sorted(keep, key=lambda s: (rank.get(s, 999), s)):
            p = ledger.account('tactical')['positions'].get(symbol)
            current = float(p['quantity']) * policy.execution_price(quotes[symbol], cfg, 'SELL') if p else 0
            used = sum(float(x['quantity']) * policy.execution_price(quotes[s], cfg, 'SELL')
                       for s, x in ledger.account('tactical')['positions'].items() if s in quotes)
            delta = min(max(0, equity * .04 - current), max(0, equity * .20 - used))
            if delta <= 0:
                proposals.append({'symbol': symbol, 'rank': rank.get(symbol),
                                  'net_forecast_pct': net.get(symbol), 'current_value_try': current,
                                  'target_value_try': current,
                                  'target_weight_pct': current / equity * 100 if equity else None,
                                  'stop': p.get('stop') if p else None, 'risk_limit_try': equity * .002})
                continue
            buy = policy.execution_price(quotes[symbol], cfg, 'BUY')
            stop_distance = max(buy * max(float(valid[symbol].get('volatility20') or 0) / 100, .005) * 2.5, buy * .02)
            stop = buy - stop_distance
            delta = _risk_limited_budget(ledger.account('tactical'), symbol, cfg, buy, stop,
                                         delta, equity * .002)
            proposals.append({'symbol': symbol, 'rank': rank.get(symbol), 'net_forecast_pct': net.get(symbol),
                              'current_value_try': current, 'target_value_try': current + delta,
                              'target_weight_pct': (current + delta) / equity * 100 if equity else None,
                              'stop': stop, 'risk_limit_try': equity * .002})
            if delta > 0 and _net_forecast(valid[symbol], forecasts[symbol], quotes[symbol], cfg, delta) >= 1:
                actions.append(_trade(ledger, cfg, quotes, now, 'tactical', symbol, 'BUY', delta,
                                      stop=stop, sector=valid[symbol].get('sector'), reason='tactical_rank_entry'))
    if _completed(actions):
        ledger.add('rebalance_check', key, now.isoformat(), book='tactical', ranks=rank,
                   net_forecasts=net, chosen=sorted(keep), proposals=proposals, policy_id=POLICY_ID)
    return actions


def _targets(ledger, cfg, records, view, spec, day):
    if spec == 'legacy-control':
        return {'policy_id': POLICY_ID, 'rows': [], 'note': 'Mevcut politika hedef ağırlık kullanmaz.'}
    equity = view['equity_try']
    positions = {(p['sleeve'], p['symbol']): p for p in view['positions']}
    rows = []
    members = sorted(core_members(records, day, cfg['market']))
    for book, share in (('core', .8), ('tactical', .2 if spec == 'core-passive' else 0)):
        if share == 0 or not members:
            continue
        for symbol in members:
            current = positions.get((book, symbol), {}).get('value_try')
            rows.append({'book': book, 'symbol': symbol, 'current_weight_pct':
                         100 * current / equity if equity and current is not None else None,
                         'target_weight_pct': 100 * share / len(members),
                         'target_kind': 'equal_weight_core' if book == 'core' else 'passive_control',
                         'policy_id': POLICY_ID})
    if spec in ('core-ridge', 'core-specialized'):
        last = next((e['data'] for e in reversed(ledger.events)
                     if e['kind'] == 'rebalance_check' and e['data'].get('book') == 'tactical'), None)
        for proposal in last.get('proposals', []) if last else []:
            symbol = proposal['symbol']
            current = positions.get(('tactical', symbol), {}).get('value_try')
            target = proposal.get('target_value_try')
            rows.append({'book': 'tactical', 'symbol': symbol,
                         'current_weight_pct': 100 * current / equity if equity and current is not None else None,
                         'target_weight_pct': 100 * target / equity if equity and target is not None else None,
                         'target_kind': 'risk_capped_tactical', 'rank': proposal.get('rank'),
                         'net_forecast_pct': proposal.get('net_forecast_pct'),
                         'stop': proposal.get('stop'), 'policy_id': POLICY_ID})
    return {'policy_id': POLICY_ID, 'rows': rows,
            'note': 'Hedefler emir değildir; fiyat, lot, masraf ve taze kotasyon tekrar doğrulanır.'}


def _presentation_view(view):
    output = copy.deepcopy(view)
    output['fill_count'] = len(view['fills'])
    output['fills'] = view['fills'][-100:]
    for part in output['parts'].values():
        part['fill_count'] = len(part['fills'])
        part['fills'] = part['fills'][-100:]
    return output


def cycle(state, frame, base, quotes, now, records, rows, forecasts, model, specialized=None, actions=()):
    """Yeni adaylar yalnız açık T0 tarihiyle başlar; mevcut hesaplara dokunmaz."""
    start = base.get('experiment_start_date')
    if not start:
        return {'status': 'T0 bekleniyor', 'policy_id': POLICY_ID, 'accounts': []}
    day = now.astimezone(IST).date().isoformat()
    if day < start:
        return {'status': 'T0 bekleniyor', 'policy_id': POLICY_ID, 'accounts': []}
    results = []
    for spec in CATALOG:
        cfg = copy.deepcopy(base)
        cfg['start_date'] = start
        path = Path(state) / 'portfolio_candidates' / spec
        ledger = Ledger(path / 'events.jsonl')
        terms = {'id': spec, 'policy_id': POLICY_ID, 'start_date': start,
                    'initial_try': cfg['initial_try'], 'monthly_try': cfg['monthly_try'],
                    'core_ratio': .8, 'tactical_ratio': .2, 'horizon_sessions': cfg['horizon_sessions'],
                    'costs': {k: cfg[k] for k in ('commission_rate', 'commission_min_try', 'commission_bsmv_rate',
                                                 'exchange_fee_rate', 'gold_buy_tax_rate', 'slippage_bps')},
                    'candidate_model': 'relative-ridge-v1' if cfg['market'] == 'bist' else 'gold-legs-ridge-v1',
                    'code_id': digest({p.name: digest(p.read_text())
                                       for p in sorted(Path(__file__).parent.glob('*.py'))})}
        prior = next((e['data'] for e in ledger.events if e['kind'] == 'portfolio_contract'), None)
        if prior is not None and any(prior.get(k) != v for k, v in terms.items()):
            raise ValueError('Ön kayıtlı aday sözleşmesi geçmişin üstüne değiştirilemez.')
        contract = prior or dict(terms, first_data_date=str(frame.date.max()) if frame is not None else None,
                                 first_data_id=(digest({'rows': len(frame),
                                                       'hash': str(__import__('pandas').util.hash_pandas_object(frame, index=False).sum())})
                                                if frame is not None else None),
                                 first_base_model_id=model.get('id'),
                                 first_specialized_model_id=specialized.get('model_id') if specialized else None)
        ledger.add('portfolio_contract', 'portfolio_contract', now.isoformat(), **contract)
        _fund(ledger, cfg, day, now, spec)
        books = ('strategy',) if spec == 'legacy-control' else ('core', 'tactical')
        cfg['blocked_symbols'].update(corporate.reconcile(ledger, actions, cfg, now, books=books))
        cfg['allowed_entry_symbols'] = sorted(universe.members(records, day)) if cfg['market'] == 'bist' else ['GRAM']
        diagnostics = []
        if spec == 'legacy-control':
            cfg['risk_multiplier'] = 1
            cfg['live_gate_passed'] = False
            decisions, fills = engine.run(ledger, list(rows.values()), forecasts, model, cfg, quotes, now)
            diagnostics = [{'status': d['code'], 'symbol': d['symbol']} for d in decisions]
        else:
            diagnostics += _core(ledger, cfg, records, rows, quotes, now)
            if spec == 'core-passive':
                diagnostics += _core(ledger, cfg, records, rows, quotes, now, book='tactical')
            elif spec in ('core-ridge', 'core-specialized'):
                active = specialized if spec == 'core-specialized' else None
                if active and active.get('ready'):
                    ranked_forecasts = active['forecasts']
                    scores = active.get('scores', ranked_forecasts)
                elif spec == 'core-ridge':
                    ranked_forecasts = forecasts
                    scores = forecasts
                else:
                    ranked_forecasts = {}
                    scores = {}
                    diagnostics.append({'status': 'özelleşmiş_model_hazır_değil'})
                if ranked_forecasts:
                    diagnostics += _tactical(ledger, cfg, rows, quotes, ranked_forecasts, scores, now)
        fee_books = books if spec == 'legacy-control' else (('portfolio', books, 'core'),)
        custody = costs.accrue(ledger, cfg, quotes, now, books=fee_books)
        view = _view(ledger, cfg, quotes, now, spec)
        target_portfolio = _targets(ledger, cfg, records, view, spec, day)
        ledger.add('portfolio_target', 'portfolio_target:' + now.isoformat(), now.isoformat(),
                   **target_portfolio)
        ledger.add('portfolio_valuation', 'portfolio_valuation:' + now.isoformat(), now.isoformat(),
                   equity_try=view['equity_try'], contributed_try=view['contributed_try'],
                   cash_try=view['cash_try'], complete=view['valuation_complete'],
                   sleeves={book: {'equity_try': part['equity_try'], 'contributed_try': part['contributed_try']}
                            for book, part in view['parts'].items()})
        ledger.save()
        result = {'id': spec, 'policy_id': POLICY_ID, 'start_date': start, 'generated_at': now.isoformat(),
                  'strategy': _presentation_view(view), 'target_portfolio': target_portfolio,
                  'diagnostics': diagnostics, 'custody': custody,
                  'automatic_promotion': False, 'model_id': model.get('id') if spec == 'core-ridge' else
                  specialized.get('model_id') if spec == 'core-specialized' and specialized else None}
        atomic_json(path / 'latest.json', result)
        results.append(result)
    return {'status': 'sanal sınav', 'policy_id': POLICY_ID, 'accounts': results,
            'comparison': compare(state, results)}


def compare(state, results):
    """Aynı tarihli katkıları ayırarak serveti ve düşüşü kıyaslar."""
    report = []
    timelines = []
    for result in results:
        ledger = Ledger(Path(state) / 'portfolio_candidates' / result['id'] / 'events.jsonl')
        observations = [e for e in ledger.events if e['kind'] == 'portfolio_valuation'
                        and e['data']['complete'] and e['data']['equity_try'] is not None]
        observations.sort(key=lambda e: e['at'])
        timelines.append(tuple(e['at'] for e in observations))
        nav, peak, worst, previous = 1.0, 1.0, 0.0, None
        for row in observations:
            equity, contributed = row['data']['equity_try'], row['data']['contributed_try']
            if previous and previous['data']['equity_try'] > 0:
                added = contributed - previous['data']['contributed_try']
                nav *= (equity - added) / previous['data']['equity_try']
            elif contributed:
                nav = equity / contributed
            peak = max(peak, nav)
            worst = min(worst, (nav / peak - 1) * 100)
            previous = row
        view = result['strategy']
        fills = [e['data'] for e in ledger.events if e['kind'] == 'fill']
        sessions = len({datetime.fromisoformat(e['at']).astimezone(IST).date() for e in observations})
        exposures = [100 * (e['data']['equity_try'] - e['data']['cash_try']) / e['data']['equity_try']
                     for e in observations if e['data'].get('cash_try') is not None and e['data']['equity_try'] > 0]
        report.append({'id': result['id'], 'wealth_try': view['equity_try'],
                       'contributed_try': view['contributed_try'],
                       'twr_pct': (nav - 1) * 100 if observations else None,
                       'max_drawdown_pct': worst if observations else None,
                       'valuations': len(observations), 'sessions': sessions,
                       'tactical_pnl_try': (view['parts'].get('tactical', {}).get('pnl_try')
                                            if view['valuation_complete'] else None),
                       'trade_count': len(fills),
                       'turnover_try': sum(f['notional_cents'] for f in fills) / 100,
                       'transaction_fees_try': sum(f['fee_cents'] for f in fills) / 100,
                       'custody_fees_try': view['account_fees_try'],
                       'average_in_market_pct': sum(exposures) / len(exposures) if exposures else None,
                       'in_market_pct': (None if view['equity_try'] is None or view['equity_try'] <= 0 else
                                         100 * (view['equity_try'] - view['cash_try']) / view['equity_try'])})
    aligned = len(set(timelines)) == 1
    passive = next((r for r in report if r['id'] == 'core-passive'), None)
    for row in report:
        row['vs_passive'] = ({'wealth_difference_try': row['wealth_try'] - passive['wealth_try'],
                              'twr_difference_pct': row['twr_pct'] - passive['twr_pct'],
                              'drawdown_not_worse': row['max_drawdown_pct'] >= passive['max_drawdown_pct']}
                             if aligned and passive and row['wealth_try'] is not None and passive['wealth_try'] is not None
                             and row['twr_pct'] is not None and passive['twr_pct'] is not None else None)
    minimum_sessions = min((r['sessions'] for r in report), default=0)
    return {'arms': report, 'aligned': aligned,
            'evaluation_status': ('Değerleme zamanları eşleşmiyor; ekonomik kıyas yapılamaz' if not aligned else
                                  '126 seans ekonomik gözlem' if minimum_sessions >= 126 else
                                  '63 seans ilk ekonomik gözlem' if minimum_sessions >= 63 else
                                  '20 seans çalışma kontrolü' if minimum_sessions >= 20 else
                                  '20 seanslık çalışma kontrolü bekleniyor'),
            'promotion': 'otomatik terfi yok'}
