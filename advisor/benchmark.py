"""Hisse başına biriken bütçe; bir eksik kotasyon tüm sepeti durdurmaz."""
from .ledger import cents


def step(ledger, cfg, quotes, symbols, now):
    from . import marketdata, policy
    symbols = sorted(set(symbols))
    if not symbols:
        return
    start = next((e for e in ledger.events if e['kind'] == 'benchmark_policy_started'), None)
    contributions = [e for e in ledger.events if e['kind'] == 'contribution' and e['data']['book'] == 'benchmark']
    if start is None:
        # Eski işlemlere dokunulmaz; geçiş anındaki kalan nakit yeni ceplere ayrılır.
        cash = ledger.account('benchmark')['cash_cents']
        shares = {s: cash // len(symbols) + (i < cash % len(symbols)) for i, s in enumerate(symbols)}
        ledger.add('benchmark_policy_started', 'benchmark:pockets:v1', now.isoformat(),
                   shares=shares, contributions=[e['key'] for e in contributions],
                   policy='equal_contribution_pockets_v1')
        start = ledger.events[-1]
    pockets = dict(start['data']['shares'])
    assigned = set(start['data']['contributions'])
    for e in ledger.events:
        if e['kind'] == 'benchmark_budget':
            assigned.add(e['data']['contribution'])
            for s, amount in e['data']['shares'].items():
                pockets[s] = pockets.get(s, 0) + amount
        elif e['kind'] == 'fill' and e['data'].get('budget_policy') == 'pockets_v1':
            d = e['data']
            pockets[d['symbol']] -= d['notional_cents'] + d['fee_cents']
    for e in contributions:
        if e['key'] in assigned:
            continue
        amount = e['data']['amount_cents']
        shares = {s: amount // len(symbols) + (i < amount % len(symbols)) for i, s in enumerate(symbols)}
        ledger.add('benchmark_budget', 'benchmark:budget:' + e['key'], now.isoformat(), contribution=e['key'], shares=shares)
        for s, n in shares.items():
            pockets[s] = pockets.get(s, 0) + n
    for symbol, budget in sorted(pockets.items()):
        if symbol not in symbols or symbol in cfg.get('blocked_symbols', {}):
            continue
        q = quotes.get(symbol)
        if marketdata.usable(q, cfg, now, cfg.get('holidays', ())):
            continue
        px = policy.execution_price(q, cfg, 'BUY')
        qty = policy.quantity_for(min(budget, ledger.account('benchmark')['cash_cents']), px, cfg)
        if not qty:
            continue
        key = f"benchmark:pocket:{symbol}:{len(ledger.events)}"
        ledger.add('fill', key, now.isoformat(), book='benchmark', symbol=symbol, side='BUY',
                   quantity=str(qty), price=px, notional_cents=cents(float(qty) * px),
                   fee_cents=policy.fee(cfg, float(qty) * px, 'BUY'), quote=q,
                   reason='accumulated_buy_hold', decision_key=key, budget_policy='pockets_v1',
                   stop=None, target=None, deadline=None)
        ledger.account('benchmark')
