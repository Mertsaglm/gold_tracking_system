"""2026-09-16: analiz kapısı stopu kapatıyor, bayat fiyat bütçeyi besliyordu."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy

import pytest

from advisor import calendar, marketdata, policy, service, risk
from advisor.ledger import Ledger, fund

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 16, 10, 30, tzinfo=timezone.utc)


def cfg():
    return {**service.configuration(ROOT), 'market': 'bist', 'initial_try': 5000, 'monthly_try': 5000,
            'max_portfolio_risk_pct': 5, 'max_positions': 5, 'max_position_pct': 20}


def quote(price=100, now=NOW):
    return {'bid': price, 'ask': price, 'quoted_at': now.isoformat(), 'source': 'fixture'}


def own(ledger, quantity='10'):
    ledger.add('fill', 'owned', (NOW-timedelta(days=1)).isoformat(), book='strategy', symbol='AAA',
               side='BUY', quantity=quantity, price=100, notional_cents=int(quantity)*10000,
               fee_cents=0, stop=95, target=120, deadline='2026-10-15', sector='bank')


def test_stale_analysis_cannot_disable_existing_stop_but_bad_quote_can(tmp_path):
    c=cfg(); l=Ledger(tmp_path/'events.jsonl');fund(l,c,'2026-09-15',NOW.isoformat());own(l)
    row={'symbol':'AAA','date':'2026-08-01','quality_ok':False,'trend50':-5,'rsi14':50,'volatility20':2}
    q=quote(90)
    d=policy.decision(row,None,{},c,q,l.account()['positions']['AAA'],None,NOW)
    assert d['action']=='SAT' and d['code']=='stop'
    assert policy.execute(l,c,[d],{'AAA':q},NOW)
    assert not l.account()['positions']
    position={'stop':95,'target':120}
    blocked=policy.decision(row,None,{},c,q,position,'Bölünme belirsiz.',NOW)
    assert blocked['action']=='VERİ BEKLENİYOR'
    bad=policy.decision(row,None,{},c,quote(90,NOW-timedelta(hours=2)),position,None,NOW)
    assert bad['action']=='VERİ BEKLENİYOR'
    new=policy.decision(row,20,{'ready':True},c,q,None,None,NOW)
    assert new['action']=='VERİ BEKLENİYOR'


def test_stale_valuation_is_not_current_profit_or_buying_power(tmp_path):
    c=cfg();l=Ledger(tmp_path/'events.jsonl');fund(l,c,'2026-09-15',NOW.isoformat());own(l)
    q=quote(200,NOW-timedelta(hours=2))
    v=policy.value_account(l.account(),{'AAA':q},c,NOW)
    assert v['equity_try'] is None and v['pnl_try'] is None and not v['valuation_complete']
    assert v['last_known_equity_try']>5000
    assert v['positions'][0]['valuation_problem']
    fresh=policy.value_account(l.account(),{'AAA':quote(200)},c,NOW)
    assert fresh['valuation_complete'] and fresh['pnl_try']>0
    d={'symbol':'BBB','action':'AL','price':100,'stop':95,'target':130,'code':'test',
       'confidence':'orta','forecast_pct':30,'reasons':[]}
    assert not policy.execute(l,c,[d],{'AAA':q,'BBB':quote()},NOW)
    assert d['code']=='incomplete_valuation'


@pytest.mark.parametrize('bad_quote',[{'bid':90}, {'bid':'90','ask':'90'}, {'bid':float('nan'),'ask':100}])
def test_malformed_quote_blocks_without_crashing_the_stop_decision(bad_quote):
    # Geçersiz fiyat önce hesaplanırsa koruma karar üretemeden çöküyordu.
    row={'symbol':'AAA','date':'2026-09-15','quality_ok':True,'close':100}
    bad_quote['quoted_at']=NOW.isoformat()
    d=policy.decision(row,None,{},cfg(),bad_quote,{'stop':95},None,NOW)
    assert d['action']=='VERİ BEKLENİYOR' and d['price'] is None


def test_half_day_is_a_session_and_yaml_comments_are_not_holidays(tmp_path):
    (tmp_path/'holidays_tr.yaml').write_text('''# measured 2026-09-16\ntam_gun:\n  "2026": [2026-10-29]\nyarim_gun:\n  "2026": [2026-10-28]\n''')
    c={**cfg(),'calendar':calendar.load(tmp_path)}
    assert service.holidays(tmp_path)==['2026-10-29']
    morning=datetime(2026,10,28,8,tzinfo=timezone.utc)
    assert marketdata.usable(quote(now=morning),c,morning) is None
    afternoon=morning+timedelta(hours=3)
    assert marketdata.usable(quote(now=afternoon),c,afternoon)
    assert calendar.add_sessions('2026-10-27',2,c)=='2026-10-30'
    row={'symbol':'AAA','date':'2026-09-15','quality_ok':True,'trend50':5,'rsi14':50,'volatility20':1}
    d=policy.decision(row,20,{'ready':True},c,quote(),None,None,NOW)
    assert d['deadline']==calendar.add_sessions(NOW.date(),c['horizon_sessions'],c)
    assert d['deadline']!=(NOW.date()+timedelta(days=30)).isoformat()


def test_spread_exactly_at_the_limit_is_not_a_false_data_failure():
    # 2026-09-16: 5150/5000 ile float hesabı %3'ü aşmış görünüyordu.
    c={**cfg(),'max_spread_pct':3}
    q={**quote(5000),'ask':5150}
    assert marketdata.usable(q,c,NOW) is None
    assert marketdata.usable({**quote(5341.288294), 'ask':5341.288294*1.03},c,NOW) is None
    assert marketdata.usable({**q,'ask':5150.01},c,NOW)


def test_benchmark_missing_symbol_and_accumulated_lot_budget(tmp_path):
    c={**cfg(),'initial_try':100,'monthly_try':100}; l=Ledger(tmp_path/'events.jsonl')
    fund(l,c,'2026-09-15',NOW.isoformat())
    service.benchmark_step(l,c,{'AAA':quote(20)},['AAA','BBB'],NOW)
    assert set(l.account('benchmark')['positions'])=={'AAA'}
    service.benchmark_step(l,c,{'AAA':quote(20),'BBB':quote(90)},['AAA','BBB'],NOW)
    assert 'BBB' not in l.account('benchmark')['positions']
    later=datetime(2026,10,1,10,30,tzinfo=timezone.utc)
    fund(l,c,'2026-10-01',later.isoformat())
    quotes={'AAA':quote(20,later),'BBB':quote(90,later)}
    service.benchmark_step(l,c,quotes,['AAA','BBB'],later)
    account=l.account('benchmark')
    assert account['positions']['BBB']['quantity']==1
    assert account['cash_cents']>=0
    before=copy.deepcopy(account)
    service.benchmark_step(l,c,quotes,['AAA','BBB'],later)
    assert l.account('benchmark')==before
    l.save();assert Ledger(l.path).account('benchmark')==before


def test_portfolio_risk_limits_new_entry_not_exit(tmp_path):
    c={**cfg(),'max_portfolio_risk_pct':.05,'risk_per_trade_pct':2}
    l=Ledger(tmp_path/'events.jsonl');fund(l,c,'2026-09-15',NOW.isoformat());own(l)
    r=risk.summary(l.account(),{'AAA':quote()},c,NOW)
    assert r['stop_risk_try']>2.5 and r['stress'][1]['loss_try']>0
    d={'symbol':'BBB','action':'AL','price':100,'stop':95,'target':130,'code':'test',
       'confidence':'orta','forecast_pct':30,'reasons':[]}
    assert not policy.execute(l,c,[d],{'AAA':quote(),'BBB':quote()},NOW)
    assert policy.execute(l,c,[{'symbol':'AAA','action':'SAT','code':'stop'}],{'AAA':quote(90)},NOW)
