"""Verildiği gün mühürlenen tahminleri yalnız vadesi dolunca çözer."""
from __future__ import annotations

import math
from collections import defaultdict

from .ledger import digest


def resolve(ledger, features, cfg, now):
    lookup = {(r['symbol'], r['date']): r for r in features.to_dict('records')}
    for e in list(ledger.events):
        if e['kind'] != 'forecast':
            continue
        d = e['data']
        row = lookup.get((d['symbol'], d['asof']))
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
                   missed_upside=d['action'] not in ('AL', 'TUT') and actual > cfg['min_expected_net_pct'])


def record(ledger, decisions, raw_forecasts, now):
    for d in decisions:
        raw = raw_forecasts.get(d['symbol'])
        if raw is None or d['forecast_pct'] is None or d['action'] == 'VERİ BEKLENİYOR':
            continue
        key = 'forecast:' + digest({'symbol': d['symbol'], 'asof': d['asof']})
        ledger.add('forecast', key, now.isoformat(), symbol=d['symbol'], asof=d['asof'],
                   action=d['action'], forecast_pct=d['forecast_pct'], raw_forecast_pct=raw,
                   model_id=d['model_id'])


def calibration(ledger, cfg):
    rows = [e['data'] for e in ledger.events if e['kind'] == 'forecast_outcome']
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
            'note': 'Hata tahmin eksi gerçekleşen fiyat değişimidir. Kaçan yükseliş, net işlem kârı değildir.'}
