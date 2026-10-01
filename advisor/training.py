"""Emir/defter oluşturmadan eğitim; gerçek katsayılar ve kapsam makbuzu."""
from pathlib import Path
import pandas as pd

from . import learning, candidates, capsule
from .ledger import digest


def bundle(frame, cfg, asof, decisions=None):
    frame = frame[frame.date <= asof].copy()
    if frame.empty:
        raise ValueError('Eğitim tarihinde fiyat verisi yok.')
    data_end = str(frame.date.max())
    watch = sorted(frame.attrs.get('live_symbols', frame.loc[frame.in_live == 1, 'symbol'].unique()))
    old = (decisions[decisions.date <= asof].drop_duplicates(['symbol', 'date'])
           if decisions is not None else pd.DataFrame(columns=['symbol', 'date']))
    versions = [('control-20-v1', cfg)] + [(s['id'], candidates.configuration(cfg, s)) for s in candidates.CATALOG]
    results = []
    for name, config in versions:
        model, features = learning.train(frame, config, data_end)
        entry = {'candidate_id': name, 'configuration': config, 'model': model}
        if model.get('ready') and model.get('kind') != 'sma50':
            names = model['features']
            valid = features.dropna(subset=names + ['forward_pct', 'label_end'])
            valid = valid[valid.quality_ok & (valid.label_end <= data_end)]
            used = valid[valid.date >= model['training_start']]
            eligible = set(zip(valid.symbol, valid.date))
            included = set(zip(used.symbol, used.date))
            keys = set(zip(old.symbol, old.date))
            entry['legacy_decision_coverage'] = {
                'unique_symbol_dates': len(keys), 'included_in_fit': len(keys & included),
                'outside_training_window': len((keys & eligible) - included),
                'unmatured_missing_or_invalid': len(keys - eligible),
                'note': 'Karar verilmiş/verilmemiş bütün geçerli fiyat örnekleri kullanılır. Eski AL/SAT kararları veya replay başarıları doğru etiket kabul edilmez.'}
            latest = features[features.date == data_end].dropna(subset=names)
            latest = latest[latest.quality_ok & latest.symbol.isin(watch)]
            entry['prediction_inputs'] = capsule.clean(latest[['symbol', 'date'] + names].to_dict('records'))
            entry['forecasts'] = dict(zip(latest.symbol, learning.predict(model, latest).tolist()))
            entry['missing_forecast_symbols'] = sorted(set(watch) - set(latest.symbol))
        results.append(entry)
    contract = {'market': cfg['market'], 'requested_asof': asof, 'data_through': data_end,
                'data_start': str(frame.date.min()), 'price_rows': len(frame),
                'price_symbols': sorted(frame.symbol.unique()), 'watchlist': watch,
                'missing_history_symbols': sorted(set(watch) - set(frame.symbol)),
                'data_hash': str(pd.util.hash_pandas_object(frame, index=False).sum()),
                'code_hash': digest({p.name: p.read_text() for p in sorted(Path(__file__).parent.glob('*.py'))})}
    return {'contract': contract, 'models': results, 'automatic_promotion': False,
            'activated': False, 'mode': 'offline_training',
            'note': 'Eğitim paketi gerçek katsayıları içerir; sanal hesaba işlem/kanıt eklemez. Sonraki cycle kendi güncel verisiyle modeli eğitir/cache kullanır. Eğitim, yatırım üstünlüğü kanıtı değildir.'}
