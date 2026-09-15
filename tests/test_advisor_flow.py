"""V2 kurallarının modüller arasında da korunduğunu kanıtlayan senaryolar."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import json
import os
import sqlite3
import subprocess

import numpy as np
import pandas as pd
import pytest

from advisor import corporate, history, learning, outcomes, policy, service
from advisor.ledger import Ledger, fund, cents

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,15,10,30,tzinfo=timezone.utc)


def fixture_quote(now=NOW,price=100):
    return {'symbol':'AAA','bid':price,'ask':price,'quoted_at':now.isoformat(),'observed_at':now.isoformat(),'source':'fixture','reference_price':100}


def frame():
    dates=pd.bdate_range(end='2026-09-14', periods=900).strftime('%Y-%m-%d')
    c=100*np.exp(np.arange(900)*.0005 + .003*np.sin(np.arange(900)*2))
    c=c/c[-1]*100
    return pd.DataFrame({'symbol':'AAA','date':dates,'close':c,'total_close':c,'high':c*1.01,'low':c*.99,'volume':1000,'in_live':1,'sector':'test'})


def test_complete_cycle_buy_repeat_restart_sell_and_monthly_funding(tmp_path, monkeypatch):
    cfg=service.configuration(ROOT)
    cfg.update(max_position_pct=40,minimum_cash_pct=20,risk_per_trade_pct=2)
    (tmp_path/'advisor').mkdir();(tmp_path/'advisor/config.json').write_text(json.dumps(cfg))
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    con.execute('CREATE TABLE corporate_actions(ticker,date,kind,value)')
    @contextmanager
    def connect(*a,**k):yield con
    monkeypatch.setattr(history,'connection',connect)
    monkeypatch.setattr(history,'load',lambda *a:frame())
    monkeypatch.setattr(history,'legacy_summary',lambda *a:{'sources':[],'recent':[]})
    monkeypatch.setattr(service.news,'collect',lambda *a,**k:{'items':[],'sources':[],'note':'fixture'})
    if cfg['market']=='bist':
        from src.calendar_bist import BistCalendar
        monkeypatch.setattr(BistCalendar,'__init__',lambda *a:None)
        monkeypatch.setattr(BistCalendar,'last_closed_session',lambda *a:NOW.date()-timedelta(days=1))
    def train(f,cfg,asof):
        return {'ready':True,'id':'fixture-model','approved':False,'asof':asof,
                'weights':[0]*len(learning.FEATURES),'mean':[0]*len(learning.FEATURES),'scale':[1]*len(learning.FEATURES),'intercept':20,
                'evaluation':{'periods':0},'limitations':[]}, learning.features(f,20)
    monkeypatch.setattr(learning,'train',train)
    s=service.cycle(tmp_path,now=NOW,quotes={'AAA':fixture_quote()},offline=True)
    assert len(s['strategy']['fills'])==1
    assert s['strategy']['fills'][0]['side']=='BUY'
    assert s['strategy']['equity_try']<5000 # Maliyet ilk anda kayıp olarak görünür.
    same=service.cycle(tmp_path,now=NOW+timedelta(minutes=1),quotes={'AAA':fixture_quote()},offline=True)
    assert len(same['strategy']['fills'])==1
    tomorrow=NOW+timedelta(days=1)
    sold=service.cycle(tmp_path,now=tomorrow,quotes={'AAA':fixture_quote(tomorrow,130)},offline=True)
    assert not sold['strategy']['positions']
    assert len(sold['strategy']['fills'])==2
    assert sold['strategy']['fills'][-1]['side']=='SELL'
    assert sold['strategy']['pnl_try']>0
    ledger=Ledger(tmp_path/'data/advisor/events.jsonl')
    fund(ledger,cfg,'2026-10-01', '2026-10-01T10:00:00+00:00');ledger.save()
    assert ledger.account()['contributed_cents']==1000000
    con.close()


def test_price_move_since_analysis_is_not_predicted_twice():
    cfg={**service.configuration(ROOT),'market':'bist'}
    row={'symbol':'AAA','date':'2026-09-14','close':100,'quality_ok':True,'trend50':2,'rsi14':50,'volatility20':1}
    d=policy.decision(row,5,{'ready':True,'approved':False},cfg,fixture_quote(price=106),None,None,NOW)
    assert d['action']=='BEKLE'
    assert d['remaining_forecast_pct']<0


def test_benchmark_return_survives_contributions_and_chart_trimming(tmp_path):
    # Al-tut eğrisi eskiden tarayıcıdaki kırpılmış pencere başında yeniden hesaplanıyordu.
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('valuation','v1',NOW.isoformat(),benchmark_try=1100,contributed_try=1000)
    ledger.add('valuation','v2',(NOW+timedelta(days=1)).isoformat(),benchmark_try=2100,contributed_try=2000)
    assert service.benchmark_nav(ledger,{'equity_try':2205,'contributed_try':2000}) == pytest.approx(1.155)
    assert service.benchmark_nav(ledger,{'equity_try':None,'contributed_try':2000}) is None


def test_brief_telegram_does_not_hide_fourth_and_fifth_sales():
    from advisor.notifications import summary
    snapshot = {'market':'bist','analysis_date':'2026-09-14',
                'strategy':{'equity_try':5000,'pnl_try':0,'cash_try':5000},
                'decisions':[{'symbol':f'AAA{i}','action':'SAT','reasons':['Zarar sınırı.'],
                              'execution':{'quantity':'2','price':100}} for i in range(5)]}
    text = summary(snapshot)
    assert len(text) <= 1000
    assert all(f'SAT · AAA{i}' in text for i in range(5))


def test_missing_gold_reference_cannot_start_a_position():
    cfg={**service.configuration(ROOT),'market':'gold'}
    q=fixture_quote();q.pop('reference_price')
    row={'symbol':'GRAM','date':'2026-09-14','quality_ok':True,'trend50':2,'rsi14':50,'volatility20':1}
    d=policy.decision(row,20,{'ready':True,'approved':False},cfg,q,None,None,NOW)
    assert d['action']=='VERİ BEKLENİYOR'


def test_outcomes_wait_for_maturity_and_do_not_count_the_same_prediction_twice(tmp_path):
    cfg=service.configuration(ROOT); l=Ledger(tmp_path/'events.jsonl')
    f=frame(); asof=f.iloc[-21]['date']; now=datetime.fromisoformat(asof+'T10:30:00+00:00')
    d={'symbol':'AAA','asof':asof,'action':'BEKLE','forecast_pct':20,'model_id':'model'}
    outcomes.record(l,[d],{'AAA':20},now)
    outcomes.record(l,[d],{'AAA':20},now)
    outcomes.resolve(l,learning.features(f[f.date<=asof],20),cfg,now)
    assert outcomes.calibration(l,cfg)['resolved_forecasts']==0
    outcomes.resolve(l,learning.features(f,20),cfg,NOW)
    outcomes.resolve(l,learning.features(f,20),cfg,NOW)
    score=outcomes.calibration(l,cfg)
    assert score['resolved_forecasts']==1 and score['independent_periods']==1
    assert score['correction_pct']==0 # Tek sonuçla kendini başarılı ilan etme.


def test_corporate_split_preserves_wealth_and_dividend_is_not_spendable_cash(tmp_path):
    cfg=service.configuration(ROOT); l=Ledger(tmp_path/'events.jsonl');fund(l,cfg,'2026-09-15',NOW.isoformat())
    l.add('fill','buy',NOW.isoformat(),book='strategy',symbol='AAA',side='BUY',quantity='10',price=100,notional_cents=100000,fee_cents=0,stop=90,target=120)
    later=NOW+timedelta(days=1)
    a={'ticker':'AAA','date':'2026-09-16','kind':'bolunme','value':2}
    assert not corporate.reconcile(l,[a],cfg,later)
    corporate.reconcile(l,[a],cfg,later)
    p=l.account()['positions']['AAA'];assert p['quantity']==20 and p['cost_cents']==100000 and p['stop']==45
    before=l.account()['cash_cents']
    corporate.reconcile(l,[{'ticker':'AAA','date':'2026-09-17','kind':'temettu','value':1}],cfg,later+timedelta(days=1))
    assert l.account()['receivable_cents']==1700
    assert l.account()['cash_cents']==before


def test_push_exhaustion_is_a_failure_not_green(tmp_path):
    """Eski for döngüsü son sleep başarılı olduğundan tüm push'lar düşse de yeşildi."""
    (tmp_path/'git').write_text('#!/bin/sh\nexit 1\n')
    (tmp_path/'sleep').write_text('#!/bin/sh\nexit 0\n')
    for p in (tmp_path/'git',tmp_path/'sleep'):p.chmod(0o755)
    p=subprocess.run(['bash',str(ROOT/'ops/push_retry.sh')],env={**os.environ,'PATH':str(tmp_path)+':'+os.environ['PATH']},capture_output=True,text=True)
    assert p.returncode==1 and p.stderr.count('deneme')==5
    (tmp_path/'git').write_text('#!/bin/sh\nexit 0\n')
    assert subprocess.run(['bash',str(ROOT/'ops/push_retry.sh')],env={**os.environ,'PATH':str(tmp_path)+':'+os.environ['PATH']},capture_output=True).returncode==0


def test_portfolio_delivery_order_and_single_writer():
    import yaml
    wf=yaml.safe_load((ROOT/'.github/workflows/portfolio.yml').read_text())
    steps=wf['jobs']['portfolio']['steps'];commands=[s.get('run','') for s in steps]
    cycle=next(i for i,s in enumerate(commands) if 'advisor cycle' in s)
    persist=next(i for i,s in enumerate(commands) if 'push_retry.sh' in s)
    notify=next(i for i,s in enumerate(commands) if 'advisor notify' in s)
    assert cycle<persist<notify
    assert wf['concurrency']['cancel-in-progress'] is False
    assert 'db dump' not in '\n'.join(commands) and 'src.dbdump' not in '\n'.join(commands)


def test_wide_spread_blocks_entries_but_does_not_disable_a_protective_exit(tmp_path):
    from advisor import marketdata
    cfg={**service.configuration(ROOT),'market':'gold'}
    q=fixture_quote(price=90);q['ask']=105
    assert marketdata.usable(q,cfg,NOW)
    assert marketdata.usable(q,cfg,NOW,allow_wide_spread=True) is None
    l=Ledger(tmp_path/'events.jsonl');fund(l,cfg,'2026-09-15',NOW.isoformat())
    l.add('fill','owned',NOW.isoformat(),book='strategy',symbol='AAA',side='BUY',quantity='1',price=100,notional_cents=10000,fee_cents=20,stop=95,target=120)
    row={'symbol':'AAA','date':'2026-09-14','quality_ok':True,'trend50':2,'rsi14':50,'volatility20':1}
    d=policy.decision(row,5,{'ready':True,'approved':False},cfg,q,l.account()['positions']['AAA'],None,NOW)
    assert d['action']=='SAT'
    assert policy.execute(l,cfg,[d],{'AAA':q},NOW)
    assert not l.account()['positions']


def test_fed_calendar_and_tcmb_timestamp_parsers():
    from advisor import news
    import xml.etree.ElementTree as ET
    h='>2026 FOMC Meetings</a><div class="fomc-meeting__month"><strong>September</strong></div><div class="fomc-meeting__date">15-16*</div>'
    assert news.fomc_calendar(h,NOW.date())[0]['date']=='2026-09-16'
    assert not news.fomc_calendar(h,NOW.date()+timedelta(days=2))
    x='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Karar</title><published>14 Eyl 2026 17:00:00</published><link href="http://www.tcmb.gov.tr/karar"/></entry></feed>'
    title,url,stamp=list(news.atom_items(ET.fromstring(x)))[0]
    assert url.startswith('https://www.tcmb.gov.tr') and stamp.utcoffset()==timedelta(hours=3)


def test_short_history_does_not_poison_the_entire_snapshot_with_nan():
    cfg={**service.configuration(ROOT),'market':'bist'}
    row={'symbol':'AAA','date':'2026-09-14','quality_ok':False,'trend50':0,'rsi14':50,'volatility20':float('nan')}
    d=policy.decision(row,None,{'ready':False},cfg,fixture_quote(),None,None,NOW)
    assert d['action']=='VERİ BEKLENİYOR'
    json.dumps(d,allow_nan=False)
