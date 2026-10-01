"""Sabit aday kataloğunun zaman sıralı offline model sınavı.

Bu rapor portföy kârı veya canlı üstünlük kanıtı değildir. Geçmiş evren
üyeliği doğrulanamadığı için BIST örneği güncel seçilmiş isimlerle sınırlıdır.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from advisor import history, learning, specialized, universe
from advisor.ledger import atomic_json, digest

LIGHTGBM = dict(num_leaves=7, max_depth=3, n_estimators=200,
                learning_rate=.03, min_child_samples=100, reg_lambda=20,
                random_state=42, n_jobs=1, verbosity=-1)


def _score(rows, forecast):
    result = rows[['date', 'symbol', 'forward_pct']].copy()
    result['prediction'] = np.asarray(forecast, dtype=float)
    return result


def _metrics(rows, market):
    if rows.empty:
        return {'rows': 0, 'dates': 0, 'mae_pct': None, 'rank_ic_mean': None,
                'rank_ic_dates': 0}
    by_date = []
    if market == 'bist':
        for _, day in rows.groupby('date'):
            if len(day) >= 3 and day.prediction.nunique() > 1 and day.forward_pct.nunique() > 1:
                ic = day.prediction.corr(day.forward_pct, method='spearman')
                if pd.notna(ic):
                    by_date.append(float(ic))
    return {'rows': len(rows), 'dates': int(rows.date.nunique()),
            'mae_pct': float((rows.prediction - rows.forward_pct).abs().mean()),
            'rank_ic_mean': float(np.mean(by_date)) if by_date else None,
            'rank_ic_dates': len(by_date)}


def evaluate(frame, market, asof, max_test_dates=126):
    horizon = 20
    f = learning.features(frame[frame.date <= asof], horizon)
    if market == 'bist':
        target, names = specialized.prepared(f, market, horizon)
        catalog = ('relative-ridge', 'relative-lightgbm')
    else:
        target = f.copy()
        names = learning.FEATURES + specialized.GOLD_LEGS
        catalog = ('gram-ridge-base', 'gram-ridge-legs')
    valid = target.dropna(subset=names + ['forward_pct', 'label_end'])
    valid = valid[(valid.label_end <= asof) & valid.quality_ok]
    dates = sorted(valid.date.unique())
    if len(dates) < 504 + horizon + 5:
        return {'status': 'yetersiz veri', 'training_dates': len(dates), 'catalog': catalog}
    evaluation_dates = dates[-max_test_dates:]
    predictions = {name: [] for name in catalog}
    folds, failures = [], []
    try:
        from lightgbm import LGBMRegressor
        lgbm_version = __import__('lightgbm').__version__
    except ImportError:
        LGBMRegressor = None
        lgbm_version = None
    for start_index in range(0, len(evaluation_dates), 5):
        block = evaluation_dates[start_index:start_index + 5]
        begin = block[0]
        # Eğitim için etiketi testin İLK günü öncesinde sonuçlanmış olmalı.
        training = valid[valid.label_end < begin]
        testing = valid[valid.date.isin(block)]
        if training.date.nunique() < 504 or testing.empty:
            failures.append({'test_start': str(begin), 'reason': 'eğitim veya test verisi eksik'})
            continue
        train_dates = sorted(training.date.unique())[-756:]
        training = training[training.date.isin(train_dates)]
        fold = {'train_start': str(training.date.min()), 'train_label_end': str(training.label_end.max()),
                'test_start': str(begin), 'test_end': str(block[-1]),
                'train_rows': len(training), 'test_rows': len(testing)}
        assert fold['train_label_end'] < fold['test_start']
        folds.append(fold)
        if market == 'bist':
            ridge = learning.fit(training, 20, names, 126, 756)
            predictions['relative-ridge'].append(_score(testing, learning.predict(ridge, testing)))
            if LGBMRegressor is not None:
                booster = LGBMRegressor(**LIGHTGBM)
                booster.fit(training[names], training.forward_pct)
                predictions['relative-lightgbm'].append(_score(testing, booster.predict(testing[names])))
        else:
            for name, selected in (('gram-ridge-base', learning.FEATURES),
                                   ('gram-ridge-legs', names)):
                ridge = learning.fit(training, 20, selected, 126, 756)
                predictions[name].append(_score(testing, learning.predict(ridge, testing)))
    metrics = {name: _metrics(pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(), market)
               for name, chunks in predictions.items()}
    return {'status': 'offline araştırma', 'market': market, 'asof': asof,
            'target': 'seçilmiş evrende göreli 20 seans getiri' if market == 'bist' else 'sentetik gram 20 seans getirisi',
            'source_limit': ('Güncel seçilmiş evren geçmiş BIST30 üyeliği değildir.' if market == 'bist' else
                             'GC=F vadeli ons ve USD/TRY; banka gerçekleşmiş getirisi değildir.'),
            'catalog': catalog, 'attempts': {name: {'parameters': LIGHTGBM if name == 'relative-lightgbm' else
                                            {'ridge_penalty': 20, 'half_life_sessions': 126, 'window_sessions': 756},
                                            'metrics': metrics[name], 'status': 'çalıştı' if metrics[name]['rows'] else
                                            'LightGBM kurulmadı' if name == 'relative-lightgbm' and LGBMRegressor is None
                                            else 'veri yok'} for name in catalog},
            'folds': folds, 'failures': failures, 'lightgbm_version': lgbm_version,
            'dsr': 'Hesaplanamadı: tam maliyetli bağımsız portföy getiri serisi yok.',
            'economic_claim': False, 'automatic_promotion': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', required=True, choices=('bist', 'gold'))
    parser.add_argument('--database', type=Path)
    parser.add_argument('--asof', type=str)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with history.connection(ROOT, args.market, args.database) as con:
        available = con.execute('SELECT max(date) FROM ' + ('bars_daily' if args.market == 'bist' else 'history_daily')).fetchone()[0]
        asof = min(available, args.asof) if args.asof else available
        frame = history.load(con, args.market, asof)
    selection_day = None
    if args.market == 'bist':
        membership = universe.read(ROOT)
        selection_day = max(asof, max(r['known_at'] for r in membership))
        selected = universe.members(membership, selection_day)
        frame = frame[frame.symbol.isin(selected)].copy()
    report = evaluate(frame, args.market, asof)
    report['selection_known_at'] = selection_day
    if selection_day and selection_day > asof:
        report['selection_warning'] = 'Evren seçimi son arşiv tarihinden sonra bilindi; bu sınav o tarihte uygulanabilir işlem sinyali değildir.'
    report['frame_id'] = digest({'market': args.market, 'asof': asof,
                                  'rows': len(frame), 'symbols': sorted(frame.symbol.unique().tolist()),
                                  'values': str(pd.util.hash_pandas_object(frame, index=False).sum())})
    output = args.output or ROOT / 'reports' / ('portfolio-model-research-' + args.market + '-' + asof + '.json')
    atomic_json(output, report)
    print(json.dumps({'output': str(output), 'status': report['status'],
                      'attempts': {k: v['status'] for k, v in report.get('attempts', {}).items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
