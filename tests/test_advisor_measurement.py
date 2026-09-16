"""Yeni ölçümün gerçek muhasebe, kaynak zamanı ve tekrar üretim sözleşmeleri."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import gzip
import json

import numpy as np
import pandas as pd
import pytest

from advisor import capsule, corporate, engine, evidence, learning, observations, reporting, service, shadow, simulation, universe
from advisor.ledger import Ledger, fund

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,16,8,tzinfo=timezone.utc)


def config():
    return {**service.configuration(ROOT),'market':'bist','initial_try':5000,'monthly_try':5000}


def quote(price=100):
    return {'bid':price,'ask':price,'quoted_at':NOW.isoformat(),'source':'fixture'}


def row():
    return {'symbol':'AAA','date':'2026-09-15','close':100,'quality_ok':True,'trend50':5,'rsi14':50,'volatility20':1}


def test_capsule_recreates_order_and_detects_tampering(tmp_path):
    cfg=config();l=Ledger(tmp_path/'events.jsonl');fund(l,cfg,'2026-09-15',NOW.isoformat())
    model={'ready':True,'approved':False,'id':'fixture'}
    context=capsule.inputs(l,[row()],{'AAA':20},model,cfg,{'AAA':quote()},NOW)
    decisions,fills=engine.run(l,[row()],{'AAA':20},model,cfg,{'AAA':quote()},NOW)
    assert len(fills)==1
    receipt=capsule.save(tmp_path,context,decisions)
    p=tmp_path/receipt['path']
    assert capsule.reproduce(p)['ok']
    bad=json.loads(gzip.decompress(p.read_bytes()));bad['payload']['context']['quotes']['AAA']['bid']=1
    p.write_bytes(gzip.compress(json.dumps(bad).encode()))
    with pytest.raises(ValueError,match='mührü'):capsule.reproduce(p)


def test_dividend_payment_is_idempotent_and_does_not_create_profit(tmp_path):
    l=Ledger(tmp_path/'events.jsonl');fund(l,config(),'2026-09-15',NOW.isoformat())
    l.add('dividend_receivable','receivable',NOW.isoformat(),book='strategy',symbol='AAA',amount_cents=1000,effective_date='2026-09-15')
    before=l.account();payment={'receivable_key':'receivable','paid_on':'2026-09-16','source_reference':'fixture-bank-statement','amount_cents':1000}
    assert corporate.settle(l,[payment],NOW)==1
    assert corporate.settle(l,[payment],NOW)==0
    after=l.account()
    assert after['cash_cents']==before['cash_cents']+1000 and after['receivable_cents']==0
    assert after['cash_cents']+after['receivable_cents']==before['cash_cents']+before['receivable_cents']
    assert after['realized_cents']==before['realized_cents']
    with pytest.raises(ValueError):corporate.settle(l,[{**payment,'amount_cents':2000}],NOW)
    with pytest.raises(ValueError):corporate.settle(l,[{**payment,'paid_on':'2026-09-17'}],NOW)


def test_many_same_day_records_do_not_promote_risk(tmp_path):
    cfg=config();l=Ledger(tmp_path/'events.jsonl')
    for i in range(100):
        l.add('valuation',str(i),(NOW+timedelta(seconds=i)).isoformat(),nav=1.1,benchmark_nav=1,equity_try=5500,contributed_try=5000,benchmark_try=5000)
    assert evidence.live(l,cfg)['periods']==0
    assert evidence.live(l,cfg)['approved'] is False
    # Aynı gün çok hisse veya tekrar koşu, bağımsız piyasa dönemi yaratmaz.
    assert not evidence.interval([1]*23,24)['approved']
    assert evidence.interval([1]*24,24)['approved']
    assert not evidence.interval([-1]*24,24)['approved']


def test_universe_uses_knowledge_date_and_keeps_delisted_history(tmp_path):
    rows=[{'symbol':'AAA','known_at':'2020-01-01','effective_from':'2020-01-01','active':True,'source':'fixture'},
          {'symbol':'AAA','known_at':'2020-03-01','effective_from':'2020-02-01','active':False,'source':'fixture'},
          {'symbol':'BBB','known_at':'2020-02-01','effective_from':'2020-02-01','active':True,'source':'fixture'}]
    assert universe.members(rows,'2020-01-15')=={'AAA'}
    assert universe.members(rows,'2020-02-15')=={'AAA','BBB'}
    assert universe.members(rows,'2020-03-15')=={'BBB'}
    p=tmp_path/'input.json';p.write_text(json.dumps(rows))
    assert universe.import_history(tmp_path,p)['records']==3
    assert universe.import_history(tmp_path,p)['records']==3
    assert universe.members(universe.read(tmp_path),'2020-01-15')=={'AAA'}


def test_shadow_waits_for_future_outcome_and_never_auto_promotes(tmp_path):
    cfg=config();l=Ledger(tmp_path/'events.jsonl')
    l.add('shadow_forecast','s',NOW.isoformat(),symbol='AAA',asof='2026-09-15',reference_id='frozen',reference_forecast=10,candidate_forecast=5)
    f=pd.DataFrame([{'symbol':'AAA','date':'2026-09-15','forward_pct':4,'label_end':'2026-10-15'}])
    shadow.resolve(l,f,NOW);assert shadow.score(l,cfg)['periods']==0
    later=NOW+timedelta(days=40)
    shadow.resolve(l,f,later);shadow.resolve(l,f,later)
    s=shadow.score(l,cfg)
    assert s['periods']==1 and s['mean_error_improvement_pct']==5
    assert not s['automatic_promotion'] and not s['approved']


def test_shadow_accounts_trade_separately_from_the_primary_account(tmp_path):
    cfg=config();l=Ledger(tmp_path/'events.jsonl');fund(l,cfg,'2026-09-15',NOW.isoformat())
    before=copy.deepcopy(l.account())
    values={name:0 for name in learning.FEATURES};values.update(row())
    rows=pd.DataFrame([values])
    model={'ready':True,'approved':False,'id':'old','asof':'2026-09-15','label_end':'2026-09-15',
           'weights':[0]*8,'mean':[0]*8,'scale':[1]*8,'intercept':20}
    result=shadow.portfolios(l,model,rows,{'AAA':0},{**model,'id':'candidate','intercept':0},cfg,{'AAA':quote()},NOW)
    assert result['ready'] and not result['automatic_promotion']
    assert l.account()==before
    assert l.account('shadow_reference')['positions'] and not l.account('shadow_candidate')['positions']
    a=copy.deepcopy(l.account('shadow_reference'))
    shadow.portfolios(l,model,rows,{'AAA':0},model,cfg,{'AAA':quote()},NOW)
    assert l.account('shadow_reference')==a
    later=NOW.replace(month=10,day=1)
    fund(l,cfg,'2026-10-01',later.isoformat())
    shadow.portfolios(l,model,rows,{'AAA':0},model,cfg,{'AAA':{**quote(),'quoted_at':later.isoformat()}},later)
    assert l.account('shadow_reference')['contributed_cents']==1000000
    assert l.account('shadow_candidate')['contributed_cents']==1000000
    l.save();assert Ledger(l.path).account('shadow_reference')==l.account('shadow_reference')


def test_weekly_contributions_and_fees_are_not_double_counted(tmp_path):
    l=Ledger(tmp_path/'events.jsonl')
    l.add('valuation','old',(NOW-timedelta(days=8)).isoformat(),equity_try=1000,contributed_try=1000,benchmark_try=1000,nav=1)
    l.add('fill','fee',NOW.isoformat(),book='strategy',side='BUY',fee_cents=100)
    l.add('valuation','new',NOW.isoformat(),equity_try=2099,contributed_try=2000,benchmark_try=2050,nav=1.099)
    w=reporting.weekly(l,NOW)
    assert w['contributions_try']==1000 and w['investment_result_try']==99
    assert w['fees_try']==1 and w['excess_try']==49
    assert reporting.funnel([{'action':'BEKLE','code':'budget','forecast_pct':2},{'action':'VERİ BEKLENİYOR','code':'data_block'}])['groups']=={'bütçe/risk':1,'veri':1}


def test_observed_cost_is_evidence_not_a_real_trade(tmp_path):
    l=Ledger(tmp_path/'events.jsonl');fund(l,config(),'2026-09-15',NOW.isoformat());before=l.account()
    r={'symbol':'AAA','side':'BUY','reference_price':100,'observed_price':101,'expected_fee_try':1,'observed_fee_try':2,'source_reference':'fixture'}
    assert observations.record(l,[r],NOW)==1 and observations.record(l,[r],NOW)==0
    assert l.account()==before
    assert observations.summary(l)['mean_adverse_price_pct']==pytest.approx(1)


def test_full_simulation_uses_next_day_price_gap_and_monthly_cash(monkeypatch):
    dates=pd.bdate_range(end='2026-10-05',periods=300).strftime('%Y-%m-%d')
    prices=np.linspace(90,100,len(dates))+.6*np.sin(np.arange(len(dates))*2)
    f=pd.DataFrame({'symbol':'AAA','date':dates,'open':prices,'close':prices,'total_close':prices,
                    'high':prices*1.001,'low':prices*.999,'volume':1000,'in_live':1,'sector':'test'})
    def train(prices,cfg,asof):
        assert prices.date.max()<='2026-10-05'
        return {'ready':True,'approved':False,'id':'fixture','asof':asof,'weights':[0]*8,'mean':[0]*8,'scale':[1]*8,'intercept':20},learning.features(prices,20)
    monkeypatch.setattr(learning,'train',train)
    cfg=config();start='2026-09-15';end='2026-10-05'
    result=simulation.simulate(f,cfg,start,end,scenario={'gap_day':'2026-09-16','gap_down_pct':20})
    assert result['fills'] and result['contributed_try']==10000 and result['cash_try']>=0
    buy=next(x for x in result['fills'] if x['side']=='BUY')
    sell=next(x for x in result['fills'] if x['side']=='SELL')
    assert sell['price']<buy['stop'] # Fiyat boşluğunda hayali stop dolumu yok.
    assert result['fees_try']>0 and not result['production_eligible']
    delayed=simulation.simulate(f,cfg,start,end,scenario={'skip_every':2})
    assert any(b['reason']=='scheduled_observation_missed' for b in delayed['blocks'])
    unknown=[{'symbol':'AAA','known_at':'2030-01-01','effective_from':'2020-01-01','active':True,'source':'fixture'}]
    missing=simulation.simulate(f,cfg,start,end,membership=unknown)
    assert not missing['fills'] and missing['universe_missing_sessions']>0
