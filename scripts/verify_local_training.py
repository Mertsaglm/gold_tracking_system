"""Yerel eğitim makbuzunu güncel arşiv/kod ve yeniden hesaplanan katsayılarla doğrula."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from advisor import history, learning, service, universe, candidates
from advisor.ledger import digest


def verify(root, report):
    payload = json.loads(report.read_text())
    contract = payload['contract']; cfg = service.configuration(root)
    assert not payload['activated'] and not payload['automatic_promotion']
    assert contract['code_hash'] == digest({p.name:p.read_text() for p in sorted((root/'advisor').glob('*.py'))})
    with history.connection(root, cfg['market']) as con:
        frame = history.load(con, cfg['market'], contract['requested_asof'])
    if cfg.get('watchlist_enabled'):
        watched = sorted(universe.members(universe.read(root), cfg['start_date']))
        frame['in_live'] = frame.symbol.isin(watched).astype(int)
        frame.attrs['live_symbols'] = watched
    assert sorted(frame.attrs['live_symbols']) == contract['watchlist']
    assert str(pd.util.hash_pandas_object(frame, index=False).sum()) == contract['data_hash']
    configs = {'control-20-v1': cfg, **{s['id']: candidates.configuration(cfg, s) for s in candidates.CATALOG}}
    assert {item['candidate_id'] for item in payload['models']} == set(configs)
    checked = []
    for item in payload['models']:
        assert item['configuration'] == configs[item['candidate_id']]
        model = item['model']
        if model.get('kind') == 'sma50':
            assert 'weights' not in model
            continue
        actual, _ = learning.train(frame, item['configuration'], contract['data_through'], evaluate=False)
        assert model['ready'] and actual['ready']
        for key in ('weights', 'mean', 'scale', 'intercept'):
            np.testing.assert_allclose(model[key], actual[key], rtol=1e-12, atol=1e-12)
        for key in ('training_rows', 'training_dates', 'training_start', 'training_end', 'label_counts'):
            assert model[key] == actual[key]
        assert model['label_end'] <= contract['data_through']
        assert all(f['train_label_end'] < f['test_start'] for f in model['folds'])
        rows = pd.DataFrame(item['prediction_inputs'])
        if not rows.empty:
            np.testing.assert_allclose(learning.predict(model, rows), [item['forecasts'][s] for s in rows.symbol])
        coverage = item['legacy_decision_coverage']
        assert coverage['unique_symbol_dates'] == sum(coverage[k] for k in
            ('included_in_fit', 'outside_training_window', 'unmatured_missing_or_invalid'))
        checked.append(item['candidate_id'])
    return {'ok': True, 'market': cfg['market'], 'retrained_and_matched': checked,
            'data_through': contract['data_through'], 'missing_history_symbols': contract['missing_history_symbols']}


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--report', type=Path, required=True)
    a=p.parse_args()
    print(json.dumps(verify(Path(__file__).resolve().parents[1], a.report), ensure_ascii=False))
