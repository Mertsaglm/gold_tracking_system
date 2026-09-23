"""Verildiği gün mühürlenen tahminleri yalnız vadesi dolunca çözer."""
from __future__ import annotations

import math
from collections import defaultdict

from .ledger import digest


def targets(features, horizon):
    """Kararın mühürlü vadesi; sonradan değişmiş forward_pct kolonunu kullanma."""
    if type(horizon) is not int or horizon < 1:
        raise ValueError('Tahmin vadesi pozitif tam sayı olmalı.')
    if 'total_close' not in features:
        raise ValueError('Tahmin sonucu için ham toplam getiri fiyat serisi gerekli.')
    result = {}
    for symbol, group in features.sort_values(['symbol', 'date']).groupby('symbol'):
        rows = group.to_dict('records')
        for i, row in enumerate(rows[:-horizon]):
            end = rows[i+horizon]
            if row['total_close'] > 0 and end['total_close'] > 0:
                result[(symbol, row['date'])] = {'label_end': end['date'],
                    'forward_pct': (end['total_close']/row['total_close']-1)*100}
    return result


def resolve(ledger, features, cfg, now):
    lookups = {}
    for e in list(ledger.events):
        if e['kind'] != 'forecast':
            continue
        d = e['data']
        horizon = d.get('horizon_sessions', 20)  # 2026-09-15 V2 eski kayıt sözleşmesi.
        if horizon not in lookups:
            lookups[horizon] = targets(features, horizon)
        row = lookups[horizon].get((d['symbol'], d['asof']))
        if not row or not isinstance(row.get('label_end'), str):
            continue
        actual = float(row['forward_pct'])
        if not math.isfinite(actual) or row['label_end'] > now.date().isoformat():
            continue
        # Sonradan düzeltilmiş fiyat serisinde oran kullanılır; banka getirisi değildir.
        ledger.add('forecast_outcome', 'outcome:' + e['key'], now.isoformat(),
                   symbol=d['symbol'], asof=d['asof'], end=row['label_end'],
                   forecast_pct=d['forecast_pct'], raw_forecast_pct=d['raw_forecast_pct'],
                   actual_pct=actual, error_pct=d['raw_forecast_pct'] - actual,
                   action=d['action'], model_id=d['model_id'],
                   horizon_sessions=horizon,
                   missed_upside=d['action'] not in ('AL', 'TUT') and actual > cfg['min_expected_net_pct'])


def record(ledger, decisions, raw_forecasts, now):
    for d in decisions:
        raw = raw_forecasts.get(d['symbol'])
        if raw is None or d['forecast_pct'] is None or d['action'] == 'VERİ BEKLENİYOR':
            continue
        identity = {'symbol': d['symbol'], 'asof': d['asof']}
        if d.get('horizon_sessions', 20) != 20:
            identity['horizon_sessions'] = d['horizon_sessions']
        key = 'forecast:' + digest(identity)
        ledger.add('forecast', key, now.isoformat(), symbol=d['symbol'], asof=d['asof'],
                   action=d['action'], forecast_pct=d['forecast_pct'], raw_forecast_pct=raw,
                   model_id=d['model_id'], horizon_sessions=d.get('horizon_sessions', 20))


def calibration(ledger, cfg):
    rows = [e['data'] for e in ledger.events if e['kind'] == 'forecast_outcome'
            and e['data'].get('horizon_sessions', 20) == cfg['horizon_sessions']]
    groups = defaultdict(list)
    for row in rows:
        groups[row['asof']].append(row)
    # Örtüşen hedef dönemlerini bağımsız kanıt sayma.
    periods, next_day = [], ''
    for day in sorted(groups):
        if day < next_day:
            continue
        group = groups[day]
        periods.append(sum(r['error_pct'] for r in group) / len(group))
        next_day = max(r['end'] for r in group)
    recent = periods[-24:]
    bias = sum(recent) / len(recent) if recent else None
    minimum = cfg['learning'].get('min_calibration_periods', 10)
    cap = cfg['learning'].get('max_bias_adjustment_pct', 2)
    correction = max(-cap, min(cap, bias)) if len(recent) >= minimum else 0.0
    return {'resolved_forecasts': len(rows), 'independent_periods': len(periods),
            'mean_error_pct': bias, 'correction_pct': correction,
            'missed_upside_count': sum(r['missed_upside'] for r in rows),
            'recent': rows[-100:],
            'note': 'Hata, tahmin eksi düzeltilmiş toplam getiri serisinin değişimidir; net banka getirisi değildir. Kaçan yükseliş, net işlem kârı değildir.'}
