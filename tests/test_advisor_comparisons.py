"""Basit rakip, tek-değişken sınavı ve rejim geçmişi için davranış sözleşmeleri."""
import copy
from datetime import timedelta
import numpy as np
import pytest
from advisor import candidates, comparisons, learning, policy, engine, simulation
from advisor.ledger import Ledger, fund
from tests.test_advisor_revision import cfg, quote, NOW
from tests.test_advisor_flow import frame


def simple_config():
    c=candidates.configuration(cfg(),candidates.CATALOG[0])
    c.update(market='bist',max_positions=5,max_position_pct=20,commission_rate=.002,require_next_quote=True)
    return c


def test_simple_rule_buys_without_forecast_exits_on_trend_and_keeps_safety(tmp_path):
    c=simple_config();model,_=learning.train(frame(),c,'2026-09-25')
    assert model['kind']=='sma50' and 'weights' not in model
    row=dict(symbol='AAA',date='2026-09-24',close=100,quality_ok=True,trend50=2,volatility20=1)
    l=Ledger(tmp_path/'events.jsonl');fund(l,c,'2026-09-25',NOW.isoformat())
    _,fills=engine.run(l,[row],{},model,c,{'AAA':quote()},NOW)
    assert not fills
    later=NOW+timedelta(minutes=30)
    decisions,fills=engine.run(l,[row],{},model,c,{'AAA':quote(later)},later)
    assert len(fills)==1 and fills[0]['fee_cents']>0
    assert decisions[0]['forecast_pct'] is None and fills[0]['target'] is None and fills[0]['deadline'] is None
    assert fills[0]['stop']>0
    row['trend50']=-1
    d=policy.decision(row,None,model,c,quote(later),l.account()['positions']['AAA'],None,later)
    assert d['action']=='SAT' and d['code']=='sma50_exit'
    row['trend50']=2
    bad=policy.decision(row,None,model,c,quote(later),None,'Bayat fiyat',later)
    assert bad['action']=='VERİ BEKLENİYOR'
    badrow=dict(row,close=float('nan'))
    assert policy.decision(badrow,None,model,c,quote(later),None,None,later)['action']!='AL'
    c['execution_phase']='valuation'
    assert not engine.run(l,[dict(row,trend50=-1)],{},model,c,{'AAA':quote(later)},later)[1]


def test_feature_removal_retrains_actual_smaller_model():
    rows=learning.features(frame(),5).dropna(subset=learning.ADAPTIVE_FEATURES+['forward_pct'])
    names=[f for f in learning.ADAPTIVE_FEATURES if f not in ('zscore20','range20')]
    m=learning.fit(rows,20,names,126,756)
    assert m['features']==names and len(m['weights'])==12
    changed=rows.copy();changed['zscore20']=1e8;changed['range20']=-1e8
    np.testing.assert_array_equal(learning.predict(m,rows),learning.predict(m,changed))


def test_comparison_contract_is_finite_and_changes_only_intended_dimension(monkeypatch):
    c=cfg();c['market']='bist';c['learning']=copy.deepcopy(c['learning'])
    plans={p['id']:p for p in comparisons.plans(c)}
    window=copy.deepcopy(plans['control']['cfg']);window['learning']['window_sessions']=756
    assert plans['window']['cfg']==window
    recency=copy.deepcopy(window);recency['learning']['half_life_sessions']=126
    assert plans['recency']['cfg']==recency
    pull=copy.deepcopy(plans['short']['cfg']);pull['entry_style']='reversion'
    assert plans['pullback']['cfg']==pull
    assert plans['bist30']['exclude']==['CCOLA','CIMSA']
    f=frame();f.attrs['live_symbols']=['AAA','CCOLA','CIMSA']
    calls=[]
    def run(f,c,start,end,**kwargs):
        calls.append((set(f.symbol),f.attrs['live_symbols'],c))
        return dict(series=[dict(date=d,nav=1+i*.001,benchmark_nav=1+i*.002,invested_pct=25.) for i,d in enumerate(sorted(f.date.unique()))],
                    fills=[],fees_try=0,custody={'pending':[]},regime_observations=[],missing_history_symbols=[],limitations=[])
    monkeypatch.setattr(comparisons,'simulate',run)
    r=comparisons.compare(f,c,min(f.date),max(f.date),{'rows':{}})
    assert len(r['results'])==len(plans)==17
    assert r['automatic_promotion'] is False and not r['production_eligible']
    assert all('difference_vs_parent' in x for x in r['results'][1:])
    assert calls[-3][1]==['AAA'] and 'bağımsız test değildir' in r['contract']['evaluation_status']


def test_simple_simulation_carries_positions_and_has_no_forecast(tmp_path):
    c=simple_config();f=frame();dates=sorted(f.date.unique())
    result=simulation.simulate(f,c,dates[-110],dates[-1],research=True)
    assert result['fills'] and result['forecast_range_pct'] is None
    assert all(x['target'] is None for x in result['fills'] if x['side']=='BUY')
    assert len(result['series'])>20 and result['series'][-1]['contributed_try']>=c['initial_try']


def test_regime_comparison_refuses_missing_and_future_inputs():
    c=simple_config();c['research_regime']='v1'
    f=frame();dates=sorted(f.date.unique())
    with pytest.raises(ValueError,match='V1 rejim girdisi'):
        simulation.simulate(f,c,dates[-3],dates[-1],research=True)
    records={d:dict(date='2099-01-01',size_multiplier=.4,cash_pct=80,max_positions=2) for d in dates}
    with pytest.raises(ValueError,match='V1 rejim girdisi'):
        simulation.simulate(f,c,dates[-3],dates[-1],scenario={'regimes':records},research=True)
    records={d:dict(date=d,label='risk-off',size_multiplier=.4,cash_pct=80,max_positions=2,
                   breadth_istenen_n=30,breadth_n=30,xu100_vs_sma200_pct=-5) for d in dates}
    result=simulation.simulate(f,c,dates[-5],dates[-1],scenario={'regimes':records},research=True)
    assert result['regime_observations'] and all(r['complete'] and r['asof']<r['date'] for r in result['regime_observations'])
