"""25 Eylül: eski hesap, saat, öğrenme ve masraf sözleşmelerinin davranış kilitleri."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from advisor import accounts, calendar, candidates, costs, engine, history, learning, marketdata, policy, service, universe
from advisor.ledger import Ledger, fund
from tests.test_advisor_flow import frame

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026,9,25,10,30,tzinfo=timezone.utc)


def cfg():
    c=service.configuration(ROOT)
    c['telegram']['enabled']=False
    return c


def quote(now=NOW, price=100):
    return dict(symbol='AAA', bid=price, ask=price, reference_price=price,
                quoted_at=now.isoformat(), observed_at=now.isoformat())


def test_new_budget_cannot_rewrite_legacy(tmp_path):
    old=Ledger(tmp_path/'data/advisor/events.jsonl')
    old.add('contribution','old',NOW.isoformat(),book='strategy',amount_cents=500000);old.save()
    checksum=old.path.read_bytes()
    c=cfg();new=Ledger(accounts.state_path(tmp_path,c)/'events.jsonl')
    fund(new,c,'2026-09-25',NOW.isoformat());fund(new,c,'2026-10-01',NOW.isoformat());new.save()
    assert new.account()['contributed_cents']==5500000
    assert new.account('benchmark')['contributed_cents']==5500000
    assert old.path.read_bytes()==checksum
    with pytest.raises(ValueError):accounts.state_path(tmp_path,{'account_id':'../bad'})


def test_missing_new_account_is_only_normal_before_its_first_due_slot(tmp_path):
    from advisor.watchdog import inspect
    (tmp_path/'advisor').mkdir()
    (tmp_path/'advisor/config.json').write_text(json.dumps(cfg()))
    (tmp_path/'holidays_tr.yaml').write_text('tam_gun:\n  "2026": []\n')
    assert inspect(tmp_path,NOW.replace(hour=4))['initializing']
    late=inspect(tmp_path,NOW)
    assert not late['ok'] and any(f['code']=='archive_invalid' for f in late['findings'])


def test_close_is_observation_not_a_fake_fill(tmp_path):
    c=cfg();c.update(market='bist', calendar={'available':True,'years':['2026'],'full_days':[],'half_days':[]},
                   execution_window={'open':'10:15','close':'18:00'}, entry_window={'open':'10:15','close':'17:45'},
                   observation_window={'open':'10:15','close':'20:00'})
    close=NOW.replace(hour=15,minute=17)
    assert calendar.phase(close,c)=='valuation'
    assert calendar.phase(close.replace(hour=14,minute=50),c)=='protection'
    assert calendar.phase(close.replace(hour=16,minute=47),c)=='valuation'
    c['execution_phase']='valuation';l=Ledger(tmp_path/'events.jsonl');fund(l,c,'2026-09-25',close.isoformat())
    row=dict(symbol='AAA',date='2026-09-24',close=100,quality_ok=True,trend50=2,rsi14=50,volatility20=1)
    decisions,fills=engine.run(l,[row],{'AAA':20},{'ready':True,'id':'x','approved':False},c,{'AAA':quote(close)},close)
    assert not fills
    assert decisions[0]['action']=='BEKLE'
    assert policy.value_account(l.account(),{},c,close)['equity_try']==50000


def test_first_signal_same_quote_and_expired_intent_cannot_fill(tmp_path):
    l=Ledger(tmp_path/'events.jsonl');c=cfg();q=quote()
    assert not marketdata.entry_ready(l,c,q,'AAA',NOW,'strategy')
    assert not marketdata.entry_ready(l,c,q,'AAA',NOW+timedelta(minutes=1),'strategy')
    later=NOW+timedelta(minutes=30)
    assert marketdata.entry_ready(l,c,quote(later),'AAA',later,'strategy')
    assert not marketdata.entry_ready(l,c,quote(later),'AAA',later,'benchmark')
    expired=NOW+timedelta(minutes=100)
    assert not marketdata.entry_ready(l,c,quote(expired),'AAA',expired,'strategy')


def test_account_fee_is_once_and_debt_survives_cash_shortfall(tmp_path):
    l=Ledger(tmp_path/'events.jsonl')
    l.add('contribution','a',NOW.isoformat(),book='strategy',amount_cents=100)
    assert l.add('account_fee','fee',NOW.isoformat(),book='strategy',amount_cents=200)
    assert not l.add('account_fee','fee',NOW.isoformat(),book='strategy',amount_cents=200)
    a=l.account();assert a['cash_cents']==0 and a['fee_liability_cents']==100
    assert policy.value_account(a,{},cfg(),NOW)['equity_try']==-1
    l.add('contribution','b',NOW.isoformat(),book='strategy',amount_cents=500)
    assert l.account()['cash_cents']==400 and l.account()['fee_liability_cents']==0
    assert l.account('benchmark')['account_fees_cents']==0


def test_later_observer_error_cannot_mutate_a_sealed_event(tmp_path):
    # Aday kontrolü hata listesine ek yapınca önceki session_check hash'i bozulmuştu.
    l=Ledger(tmp_path/'events.jsonl');errors=[]
    l.add('session_check','check',NOW.isoformat(),errors=errors)
    errors.append('later candidate failure')
    l.save()
    assert Ledger(l.path).events[0]['data']['errors']==[]


def test_missing_custody_days_do_not_become_zero_fee(tmp_path):
    c=cfg();c.update(market='bist',custody={'enabled':True,'source':'fixture','bsmv_rate':.05,'bands':[{'up_to_try':None,'fee_try':115}]})
    assert costs.quarterly_fee(50000,c['custody'])==12075
    l=Ledger(tmp_path/'events.jsonl');fund(l,c,'2026-09-25',NOW.isoformat())
    result=costs.accrue(l,c,{},NOW.replace(month=10,day=1))
    assert result['pending'] and not any(e['kind']=='account_fee' for e in l.events)


def test_recency_is_date_weighted_and_future_prices_do_not_change_features():
    f=frame();past=learning.features(f,5)
    changed=f.copy();changed.loc[changed.date>'2026-08-01','total_close']*=2
    after=learning.features(changed,5)
    pd.testing.assert_frame_equal(past.loc[past.date<='2026-08-01',learning.ADAPTIVE_FEATURES],after.loc[after.date<='2026-08-01',learning.ADAPTIVE_FEATURES])
    rows=past.dropna(subset=learning.FEATURES+['forward_pct']).copy()
    rows['forward_pct']=0.;rows.loc[rows.index[-80:],'forward_pct']=10.
    old=learning.fit(rows,20);recent=learning.fit(rows,20,half_life_sessions=20)
    assert recent['intercept']>old['intercept']+5
    assert len(learning.predict(recent,rows))==len(rows)


def test_dated_watchlist_does_not_know_future_membership():
    if cfg()['market']!='bist':pytest.skip('BIST üyeliği BIST deposunda tutulur.')
    rows=universe.read(ROOT)
    assert not universe.members(rows,'2026-09-24')
    september=universe.members(rows,'2026-09-25');october=universe.members(rows,'2026-10-01')
    assert len(september)==len(october)==32
    assert 'DSTKF' in september and 'TRMET' not in september
    assert 'DSTKF' not in october and 'TRMET' in october
    assert {'TRALT','SASA','CCOLA','CIMSA'}<=september


def test_reversion_is_a_different_entry_rule_not_a_renamed_model():
    c=cfg();c.update(market='bist',horizon_sessions=5)
    row=dict(symbol='AAA',date='2026-09-24',close=100,quality_ok=True,trend50=-2,
             trend200=2,zscore20=-1.5,daily_jump_pct=1,rsi14=40,volatility20=1)
    m=dict(ready=True,id='fixture',approved=False,horizon_sessions=5)
    assert policy.decision(row,20,m,c,quote(),None,None,NOW)['action']=='BEKLE'
    c['entry_style']='reversion'
    assert policy.decision(row,20,m,c,quote(),None,None,NOW)['action']=='AL'


def test_training_cannot_read_future_labels_from_feature_cache():
    c=cfg();c['learning']['min_training_dates']=300
    f=frame();asof='2026-06-01';prepared=learning.features(f,c['horizon_sessions'])
    direct,_=learning.train(f,c,asof,evaluate=False)
    cached,_=learning.train(f,c,asof,evaluate=False,prepared_features=prepared)
    assert cached['weights']==pytest.approx(direct['weights'])
    assert cached['label_end']<=asof


def test_new_cycle_runs_candidates_with_separate_budget_and_horizon(tmp_path,monkeypatch):
    c=cfg();c['watchlist_enabled']=False
    (tmp_path/'advisor').mkdir();(tmp_path/'advisor/config.json').write_text(json.dumps(c))
    data=frame();data['date']=data.date.map(lambda d:(datetime.fromisoformat(d)+timedelta(days=10)).date().isoformat())
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    con.execute('CREATE TABLE corporate_actions(ticker,date,kind,value)')
    @contextmanager
    def connection(*args,**kwargs):yield con
    monkeypatch.setattr(history,'connection',connection)
    monkeypatch.setattr(history,'load',lambda *a:data.copy())
    monkeypatch.setattr(history,'legacy_summary',lambda *a:{'sources':[],'recent':[]})
    monkeypatch.setattr(service.news,'collect',lambda *a,**k:{'items':[],'sources':[],'upcoming':[]})
    if c['market']=='bist':
        from src.calendar_bist import BistCalendar
        monkeypatch.setattr(BistCalendar,'__init__',lambda *a:None)
        monkeypatch.setattr(BistCalendar,'last_closed_session',lambda *a:NOW.date()-timedelta(days=1))
    real_train=learning.train
    def train(f,c,asof):
        if c.get('strategy_kind')=='sma50':return real_train(f,c,asof)
        m={'ready':True,'id':'model-'+str(c['horizon_sessions']),'horizon_sessions':c['horizon_sessions'],
           'approved':False,'asof':asof,'features':learning.FEATURES,'weights':[0]*8,'mean':[0]*8,'scale':[1]*8,
           'intercept':20,'evaluation':{'periods':0},'limitations':[]}
        return m,learning.features(f,c['horizon_sessions'])
    monkeypatch.setattr(learning,'train',train)
    one=service.cycle(tmp_path,now=NOW,quotes={'AAA':quote()},offline=True)
    assert one['account_id']=='paper-2026-09-25' and len(one['candidates'])==4
    assert not one['strategy']['fills']
    later=NOW+timedelta(minutes=30)
    two=service.cycle(tmp_path,now=later,quotes={'AAA':quote(later)},offline=True)
    assert len(two['strategy']['fills'])==1
    assert (tmp_path/'data/advisor/latest.json').exists()
    assert not (tmp_path/'data/advisor/events.jsonl').exists()
    for candidate in two['candidates']:
        assert candidate['strategy']['contributed_try']==50000
        assert candidate['benchmark']['contributed_try']==50000
        assert candidate['automatic_promotion'] is False
        path=accounts.state_path(tmp_path,c)/'candidates'/candidate['id']/'events.jsonl'
        rows=[e['data'] for e in Ledger(path).events if e['kind']=='forecast']
        if candidate['style']=='sma50':assert not rows
        else:assert rows and all(r['horizon_sessions']==candidate['horizon'] for r in rows)
    if c['market']=='bist':
        late=NOW.replace(hour=19,minute=30)  # İstanbul 22:30: normal gözlem penceresinden sonra.
        close=service.cycle(tmp_path,now=late,quotes={'AAA':quote(late,130)},offline=True,closing_refresh=True)
        assert close['monitoring']['phase']=='valuation'
        assert len(close['strategy']['fills'])==len(two['strategy']['fills'])
        assert close['strategy']['valuation_complete']
    def failed_candidate(*a,**k):
        raise RuntimeError('fixture')
    monkeypatch.setattr(candidates,'cycle',failed_candidate)
    failed_at=late+timedelta(minutes=1) if c['market']=='bist' else later+timedelta(minutes=1)
    failed=service.cycle(tmp_path,now=failed_at,quotes={'AAA':quote(failed_at)},offline=True,closing_refresh=c['market']=='bist')
    assert failed['candidates']==[] and any('Aday sınavı' in e for e in failed['health']['errors'])
    assert (accounts.state_path(tmp_path,c)/'latest.json').exists()
    from advisor import recovery
    backup=tmp_path/'recovery.zip'
    recovery.backup(tmp_path,backup)
    assert recovery.drill(backup)['cash_cents']['strategy']==Ledger(accounts.state_path(tmp_path,c)/'events.jsonl').account()['cash_cents']
    con.close()
