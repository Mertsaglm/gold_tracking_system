"""Toplam risk gözlemi; mevcut pozisyonların satışını durdurmaz."""
from .ledger import cents


def summary(account, quotes, cfg, now):
    from .policy import execution_price, fee
    from .marketdata import price_problem
    rows, missing = [], []
    for symbol, p in account['positions'].items():
        q = quotes.get(symbol)
        if price_problem(q, cfg, now):
            missing.append(symbol)
            continue
        price, qty = execution_price(q, cfg, 'SELL'), float(p['quantity'])
        stop = p.get('stop')
        value = cents(qty * price) - fee(cfg, qty * price, 'SELL')
        stop_value = cents(qty * stop) - fee(cfg, qty * stop, 'SELL') if stop else 0
        rows.append({'symbol': symbol, 'sector': p.get('sector'), 'value_try': value / 100,
                     'stop_risk_try': max(0, value - stop_value) / 100})
    equity = (account['cash_cents'] + account.get('receivable_cents', 0)) / 100 + sum(r['value_try'] for r in rows)
    risk = sum(r['stop_risk_try'] for r in rows)
    return {'complete': not missing, 'missing': missing, 'positions': rows,
            'stop_risk_try': risk if not missing else None,
            'stop_risk_pct': risk / equity * 100 if equity > 0 and not missing else None,
            'limit_pct': cfg.get('max_portfolio_risk_pct', 5),
            'stress': [{'fall_pct': drop, 'loss_try': sum(r['value_try'] for r in rows) * drop / 100 if not missing else None}
                       for drop in (5, 10, 20)],
            'note': 'Tüm varlıkların birlikte düşüş senaryosu; olasılık tahmini değildir. Stop fiyatında satış garantisi yoktur.'}
