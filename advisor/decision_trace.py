"""Karar kapılarının sayısal izi; mevcut politika sonucunu değiştirmez."""
from __future__ import annotations

import math

from .policy import execution_price, fee


def describe(row, forecast, decision, quote, cfg, now):
    """Her kontrolü geçti/kaldı/değerlendirilmedi olarak ayrı raporla."""
    symbol = row['symbol']
    checks = []

    def add(name, observed=None, threshold=None, passed=None, note=None):
        checks.append({'check': name, 'observed': observed, 'threshold': threshold,
                       'status': 'değerlendirilmedi' if passed is None else 'geçti' if passed else 'kaldı',
                       'note': note})

    from .marketdata import usable
    quote_problem = usable(quote, cfg, now, cfg.get('holidays', ()),
                           allow_wide_spread=decision.get('action') in ('SAT', 'TUT'))
    analysis_date = cfg.get('expected_analysis_date')
    fresh = bool(row.get('quality_ok')) and (not analysis_date or row.get('date') == analysis_date)
    add('veri', row.get('date'), analysis_date, fresh and quote_problem is None,
        quote_problem or (None if fresh else 'Analiz kapanışı eksik veya geçersiz.'))
    add('tahmin', forecast, None, forecast is not None if fresh else None)
    if not fresh or quote_problem or forecast is None or not quote:
        for name in ('maliyet', 'trend', 'rsi', 'kazanc_risk', 'butce', 'dolum'):
            add(name)
        return checks

    reference = quote.get('reference_price') if cfg['market'] == 'gold' else quote.get('bid')
    close = row.get('close')
    if (not isinstance(close, (int, float)) or not math.isfinite(close) or close <= 0 or
            not isinstance(reference, (int, float)) or isinstance(reference, bool) or
            not math.isfinite(reference) or reference <= 0):
        for name in ('maliyet', 'trend', 'rsi', 'kazanc_risk', 'butce', 'dolum'):
            add(name)
        return checks
    remaining = (close * (1 + forecast / 100) / reference - 1) * 100
    buy, sell = execution_price(quote, cfg, 'BUY'), execution_price(quote, cfg, 'SELL')
    roundtrip = (buy / sell - 1) * 100 + (fee(cfg, 1000, 'BUY') + fee(cfg, 1000, 'SELL')) / 1000
    net = remaining - roundtrip
    add('maliyet', round(net, 6), cfg['min_expected_net_pct'], net >= cfg['min_expected_net_pct'])
    if cfg.get('entry_style') == 'reversion':
        add('geri_cekilme', row.get('zscore20'), -1,
            row.get('zscore20') is not None and row['zscore20'] < -1)
        add('uzun_trend', row.get('trend200'), -10,
            row.get('trend200') is not None and row['trend200'] > -10)
        add('ani_hareket', row.get('daily_jump_pct'), 5,
            row.get('daily_jump_pct') is not None and row['daily_jump_pct'] < 5)
    else:
        add('trend', row.get('trend50'), 0, row.get('trend50') is not None and row['trend50'] > 0)
        add('rsi', row.get('rsi14'), 75, row.get('rsi14') is not None and row['rsi14'] < 75)
    rr = None
    if decision.get('stop') and decision.get('target'):
        size = 1000 / buy
        buy_fee = fee(cfg, 1000, 'BUY') / 100 / size
        risk = buy - decision['stop'] + buy_fee + fee(cfg, size * decision['stop'], 'SELL') / 100 / size
        reward = decision['target'] - buy - buy_fee - fee(cfg, size * decision['target'], 'SELL') / 100 / size
        rr = reward / risk if risk > 0 else 0
    add('kazanc_risk', round(rr, 6) if rr is not None else None,
        cfg['min_net_reward_risk'], rr >= cfg['min_net_reward_risk'] if rr is not None else None)
    budget_codes = {'budget', 'capacity', 'sector_cap', 'same_day_exit', 'incomplete_valuation', 'portfolio_risk'}
    add('butce', decision.get('code'), None,
        False if decision.get('code') in budget_codes else True if decision.get('execution') else None,
        'Yalnız alım adayı uygulama aşamasında ölçülür.')
    add('dolum', bool(decision.get('execution')), None,
        bool(decision.get('execution')) if decision.get('action') == 'AL' else None)
    return checks
