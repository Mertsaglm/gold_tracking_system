"""Ön kayıtlı ek Ridge modelleri; yalnız yeni sanal adayları besler."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import learning
from .ledger import atomic_json, digest


GOLD_LEGS = [f'{prefix}_{name}' for prefix in ('ons', 'usdtry')
             for name in ('momentum20', 'momentum60', 'volatility20', 'trend50')]


def prepared(features, market, horizon):
    f = features.copy()
    if market == 'bist':
        if horizon != 20:
            raise ValueError('Göreli modelin vadesi 20 seans olmalı.')
        # Her tarihin referansı, o tarihli seçilmiş evrenin eşit ağırlıklı
        # gerçekleşmiş toplam getirisidir; tarihsel endeks üyeliği iddiası yok.
        reference = f.groupby('date').forward_pct.transform('mean')
        f['forward_pct'] = f.forward_pct - reference
        names = learning.ADAPTIVE_FEATURES
    else:
        names = learning.FEATURES + GOLD_LEGS
        if not set(GOLD_LEGS) <= set(f):
            raise ValueError('Altın ons/kur özellikleri eksik.')
    return f, names


def fit_candidate(features, market, horizon, asof):
    f, names = prepared(features[features.date <= asof], market, horizon)
    valid = f.dropna(subset=names + ['forward_pct', 'label_end'])
    valid = valid[(valid.label_end <= asof) & valid.quality_ok]
    if valid.date.nunique() < 504:
        return {'ready': False, 'reason': '504 tamamlanmış eğitim seansı henüz yok.',
                'training_dates': int(valid.date.nunique())}
    model = learning.fit(valid, 20, names, 126, 756)
    model.update(ready=True, asof=str(asof), market=market, horizon_sessions=horizon,
                 target='relative_total_return_pct' if market == 'bist' else 'gram_theoretical_return_pct',
                 training_label_end=str(valid.label_end.max()),
                 limitations=(['Seçilmiş evrenin eşit ağırlıklı getirisi; tarihsel BIST30 iddiası yok.']
                              if market == 'bist' else
                              ['Ons kaynağı GC=F vadeli kontratı; spot XAUUSD değil.',
                               'Gram hedefi sentetiktir; banka makası/vergisi işlem katmanındadır.']))
    model['id'] = digest({k: model[k] for k in ('asof', 'target', 'features', 'weights',
                                               'intercept', 'mean', 'scale', 'training_label_end')})[:16]
    return model


def _causal_input_id(features, through):
    columns = [c for c in ('symbol', 'date', 'close', 'total_close', 'high', 'low',
                           'volume', 'ons_usd', 'usdtry') if c in features]
    prefix = features.loc[features.date <= through, columns]
    return digest({'rows': len(prefix), 'hash': str(pd.util.hash_pandas_object(prefix, index=False).sum())})


def current(state, features, cfg, base_forecasts, rows):
    """Yeni aday beş tamamlanmış seansta bir öğrenir; ara seanslarda modeli dondurur."""
    state = Path(state)
    cache = state / 'specialized_model.json'
    dates = sorted(str(d) for d in features.date.unique())
    asof = dates[-1]
    old = json.loads(cache.read_text()) if cache.exists() else {}
    source_id = digest({'specialized': Path(__file__).read_text(), 'features': Path(learning.__file__).read_text()})
    stale = (old.get('market') != cfg['market'] or old.get('horizon_sessions') != cfg['horizon_sessions']
             or old.get('asof') not in dates or dates.index(old['asof']) + 5 <= len(dates) - 1
             or old.get('training_input_hash') != _causal_input_id(features, old['asof'])
             or old.get('source_id') != source_id)
    if stale:
        old = fit_candidate(features, cfg['market'], cfg['horizon_sessions'], asof)
        if old.get('ready'):
            old['training_input_hash'] = _causal_input_id(features, asof)
            old['source_id'] = source_id
            atomic_json(cache, old)
    if not old.get('ready'):
        return old
    valid = rows.dropna(subset=old['features']).copy()
    predicted = dict(zip(valid.symbol, learning.predict(old, valid).tolist()))
    if cfg['market'] == 'bist':
        return {'ready': True, 'model_id': old['id'], 'model_asof': old['asof'],
                'target': old['target'], 'forecasts': base_forecasts,
                'scores': predicted, 'training_label_end': old['training_label_end']}
    return {'ready': True, 'model_id': old['id'], 'model_asof': old['asof'],
            'target': old['target'], 'forecasts': predicted,
            'scores': predicted, 'training_label_end': old['training_label_end']}
