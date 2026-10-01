"""Eksik takvim ve gerçekte kullanılmayan eğitim satırı sessiz başarı olamaz."""
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from advisor import calendar, comparisons, experiments, learning, simulation, training
from tests.test_advisor_flow import frame
from tests.test_advisor_revision import cfg


@pytest.mark.parametrize('runner', [simulation.simulate, experiments.compare, comparisons.compare])
def test_missing_calendar_year_rejects_research_instead_of_cash_performance(runner):
    c = cfg()
    c['calendar'] = {'available': True, 'years': ['2026'], 'full_days': [], 'half_days': []}
    with pytest.raises(ValueError, match='2025'):
        runner(frame(), c, '2025-09-01', '2026-09-14')


def test_historical_calendar_is_present_and_holidays_are_excluded():
    c = cfg(); c['calendar'] = calendar.load(Path(__file__).resolve().parents[1])
    calendar.require_coverage('2025-09-01', '2026-09-25', c)
    assert not calendar.trading_day('2025-10-29', c)
    assert calendar.trading_day('2025-10-28', c)
    assert '2025-10-28' in c['calendar']['half_days']


def test_effective_training_receipt_matches_window_and_keeps_losses():
    f = frame()
    # Tek yönlü fixture, zarar örneklerinin kaybolmasını yakalayamaz.
    prices = 100 * np.exp(.05 * np.sin(np.arange(len(f)) / 20))
    f['close'] = f['total_close'] = prices
    f['high'] = prices * 1.01; f['low'] = prices * .99
    c = cfg(); c['learning'].update(window_sessions=100, half_life_sessions=30)
    m, features = learning.train(f, c, f.date.max(), evaluate=False)
    rows = features.dropna(subset=m['features'] + ['forward_pct', 'label_end'])
    rows = rows[rows.quality_ok & (rows.label_end <= m['asof'])]
    used = rows[rows.date.isin(sorted(rows.date.unique())[-100:])]
    assert m['available_training_rows'] > m['training_rows'] == len(used)
    assert m['training_dates'] == 100
    assert m['training_start'] == used.date.min()
    assert m['training_end'] == used.date.max() < m['label_end'] <= m['asof']
    assert m['label_counts']['positive'] > 0 and m['label_counts']['negative'] > 0
    assert sum(m['label_counts'].values()) == len(used)
    expected = learning.fit(used, c['learning']['ridge_penalty'], m['features'], 30)
    np.testing.assert_allclose(m['weights'], expected['weights'])


def test_training_bundle_preserves_coefficients_without_manufacturing_live_evidence(tmp_path):
    f = frame(); f.attrs['live_symbols'] = ['AAA', 'MISSING']
    c = cfg(); original = copy.deepcopy(c)
    decisions = pd.DataFrame([{'symbol': 'AAA', 'date': f.date.iloc[-40], 'action': 'AL'},
                              {'symbol': 'AAA', 'date': f.date.iloc[-40], 'action': 'SAT'},
                              {'symbol': 'AAA', 'date': f.date.iloc[-1], 'action': 'BEKLE'}])
    result = training.bundle(f, c, f.date.max(), decisions)
    path = tmp_path / 'training.json'
    path.write_text(json.dumps(result, allow_nan=False))
    saved = json.loads(path.read_text())
    assert c == original and not result['activated'] and not result['automatic_promotion']
    assert result['contract']['missing_history_symbols'] == ['MISSING']
    assert len(saved['models']) == 5
    for item in saved['models']:
        m = item['model']
        if m.get('kind') == 'sma50':
            assert 'weights' not in m
            continue
        rows = pd.DataFrame(item['prediction_inputs'])
        assert learning.predict(m, rows)[0] == pytest.approx(item['forecasts']['AAA'])
        assert item['missing_forecast_symbols'] == ['MISSING']
        assert item['legacy_decision_coverage']['unique_symbol_dates'] == 2
        assert item['legacy_decision_coverage']['included_in_fit'] == 1
        assert item['legacy_decision_coverage']['unmatured_missing_or_invalid'] == 1
        assert all(fold['train_label_end'] < fold['test_start'] for fold in m['folds'])
    assert not list(tmp_path.rglob('events.jsonl'))


def test_quarter_start_holiday_carries_known_prior_session_not_a_missing_mark(tmp_path):
    from datetime import datetime
    from advisor import costs
    from advisor.ledger import Ledger
    c=cfg();c.update(market='bist',start_date='2025-12-31',calendar={
        'available':True,'years':['2025','2026'],'full_days':['2026-01-01'],'half_days':[]})
    c['custody']={'enabled':True,'source':'fixture','bsmv_rate':0,'bands':[{'up_to_try':None,'fee_try':10}]}
    ledger=Ledger(tmp_path/'events.jsonl')
    days=pd.bdate_range('2025-12-31','2026-03-31').strftime('%Y-%m-%d')
    for d in days:
        if d=='2026-01-01':continue
        ledger.add('custody_mark',d,d+'T17:30:00+03:00',book='strategy',day=d,value_try=100.)
    r=costs.accrue(ledger,c,{},datetime.fromisoformat('2026-04-01T10:30:00+03:00'),books=('strategy',))
    assert not r['pending']
    fee=next(e['data'] for e in ledger.events if e['key']=='custody:strategy:2026-01-01')
    assert fee['average_securities_try']==100


def test_gold_without_intraday_prices_exits_at_next_observed_price(monkeypatch):
    f=frame()
    extra=pd.DataFrame([dict(f.iloc[-1],date='2026-09-15',open=100.,close=90.,total_close=90.,high=90.,low=90.),
                        dict(f.iloc[-1],date='2026-09-16',open=90.,close=90.,total_close=90.,high=90.,low=90.)])
    f=pd.concat([f,extra],ignore_index=True)
    def train(data,c,asof):
        return {'ready':True,'approved':False,'id':'fixture','asof':asof,'horizon_sessions':20,
                'weights':[0]*8,'mean':[0]*8,'scale':[1]*8,'intercept':50},learning.features(data,20)
    monkeypatch.setattr(learning,'train',train)
    c=cfg();c['market']='gold'
    r=simulation.simulate(f,c,'2026-09-15','2026-09-16')
    buy=next(x for x in r['fills'] if x['side']=='BUY')
    sell=next(x for x in r['fills'] if x['side']=='SELL')
    assert buy['at'].startswith('2026-09-15')
    assert sell['at'].startswith('2026-09-16')
    assert sell['price']==90 and sell['price']<buy['stop']


def test_zero_volume_bar_can_mark_but_cannot_fill(monkeypatch):
    # Gerçek seans günündeki sıfır hacimli barı silmek de, onunla işlem
    # yapmak da yanlış: günlük referans korunur, dolum kapalı kalır.
    f=frame();day=f.date.max();f.loc[f.date==day,'volume']=0
    def train(data,c,asof):
        return {'ready':True,'approved':False,'id':'fixture','asof':asof,'horizon_sessions':20,
                'weights':[0]*8,'mean':[0]*8,'scale':[1]*8,'intercept':50},learning.features(data,20)
    monkeypatch.setattr(learning,'train',train)
    c=cfg();c['market']='bist'
    r=simulation.simulate(f,c,day,day)
    assert not r['fills'] and not r['benchmark_fills']
    assert r['series'][0]['nav']==1
    assert r['decision_counts'].get('data_block')==1
