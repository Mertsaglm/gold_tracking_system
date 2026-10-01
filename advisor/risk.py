"""Toplam risk gözlemi; mevcut pozisyonların satışını durdurmaz."""
from .ledger import cents


def summary(account, quotes, cfg, now):
    from .policy import execution_price, fee
    from .marketdata import price_problem
    rows, missing = [], []
    for symbol, p in account['positions'].items():
        q = quotes.get(symbol)
        if cfg.get('blocked_symbols', {}).get(symbol) or price_problem(q, cfg, now):
            missing.append(symbol)
            continue
        price, qty = execution_price(q, cfg, 'SELL'), float(p['quantity'])
        stop = p.get('stop')
        value = cents(qty * price) - fee(cfg, qty * price, 'SELL')
        stop_value = cents(qty * stop) - fee(cfg, qty * stop, 'SELL') if stop else 0
        rows.append({'symbol': symbol, 'sector': p.get('sector'), 'value_try': value / 100,
                     'stop_risk_try': max(0, value - stop_value) / 100})
    equity = (account['cash_cents'] + account.get('receivable_cents', 0) - account.get('fee_liability_cents', 0)) / 100 + sum(r['value_try'] for r in rows)
    risk = sum(r['stop_risk_try'] for r in rows)
    return {'complete': not missing, 'missing': missing, 'positions': rows,
            'stop_risk_try': risk if not missing else None,
            'stop_risk_pct': risk / equity * 100 if equity > 0 and not missing else None,
            'limit_pct': cfg.get('max_portfolio_risk_pct', 5),
            'stress': [{'fall_pct': drop, 'loss_try': sum(r['value_try'] for r in rows) * drop / 100 if not missing else None}
                       for drop in (5, 10, 20)],
            'note': 'Tüm varlıkların birlikte düşüş senaryosu; olasılık tahmini değildir. Stop fiyatında satış garantisi yoktur.'}


def control(current, learned, cfg):
    """Geçmişe bakan, sınırlı risk azaltımı. Sermaye kaybını piyasa bahanesiyle silmez."""
    import math
    policy = cfg.get('adaptive_risk', {})
    result = {'multiplier': 1.0, 'regime': 'ölçüm kapalı', 'reasons': [],
              'account_drawdown_pct': learned.get('drawdown_pct'),
              'note': 'Piyasa koşulu risk ayarıdır; model üstünlüğü kanıtı değildir. Model değişimi kaybı sıfırlamaz.'}
    if not policy.get('enabled') or current.empty:
        return result
    rows = current[current.quality_ok == True]
    if 'expected_analysis_date' in cfg:
        rows = rows[rows.date == cfg['expected_analysis_date']]
    if rows.empty:
        result.update(multiplier=.25, regime='veri eksik', reasons=['Rejim girdisi eksik; yeni pozisyon riski azaltıldı.'])
        return result
    vol = float(rows.volatility20.median())
    trend = float(rows.trend50.median())
    result.update(volatility20_pct=vol if math.isfinite(vol) else None, trend50_pct=trend if math.isfinite(trend) else None)
    if math.isfinite(vol) and vol > 0:
        result['multiplier'] = min(1., max(.25, policy.get('target_daily_vol_pct', 2.) / vol))
    result['regime'] = 'zayıf trend' if trend < 0 else 'pozitif trend'
    if trend < 0:
        result['multiplier'] *= .5
        result['reasons'].append('Son kapanışlar 50 seans ortalamasının altında; yeni risk yarıya indirildi.')
    if result['multiplier'] < 1:
        result['reasons'].append('Risk artışı yapılmaz; satış ve öğrenme hattı çalışmaya devam eder.')
    return result
