"""2026-09-22: üretim incelemesinde bulunan sessiz hata sınıfları."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import json
import sqlite3

import pandas as pd
import pytest

from tests.advisor_legacy import legacy_configuration

from advisor import history, marketdata, notifications, outcomes, policy, service, shadow
from advisor.ledger import Ledger, fund

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 22, 10, tzinfo=timezone.utc)


def cfg():
    return {**legacy_configuration(ROOT), 'market': 'bist'}


def snapshot(action='BEKLE', code='no_edge', now=NOW):
    return {'market': 'bist', 'generated_at': now.isoformat(), 'analysis_date': '2026-09-21',
            'health': {'errors': [], 'ledger_hash': 'test'},
            'strategy': {'equity_try': 5000, 'pnl_try': 0, 'cash_try': 5000},
            'decisions': [{'symbol': 'AAA', 'action': action, 'code': code, 'reasons': ['fixture']}]}


def test_telegram_reports_recovery_even_if_state_was_sent_earlier(tmp_path, monkeypatch):
    # Üretimde BEKLE -> VERİ BEKLENİYOR -> BEKLE, son uyarıyı ekranda bırakıyordu.
    sent = []
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test')
    class Response:
        status_code = 200
        def json(self): return {'ok': True, 'result': {'message_id': len(sent), 'date': 1790071200}}
    def post(*args, **kwargs):
        sent.append(kwargs['json']['text'])
        return Response()
    monkeypatch.setattr(notifications.requests, 'post', post)
    l = Ledger(tmp_path/'events.jsonl'); c = cfg()
    results = []
    for i, s in enumerate([snapshot(), snapshot('VERİ BEKLENİYOR', 'data_block'), snapshot()]):
        at = NOW + timedelta(minutes=i)
        s['generated_at'] = at.isoformat()
        results.append(notifications.publish(tmp_path, c, s, l, at))
    assert results == [True, True, True]
    assert notifications.delivered(l, s)
    assert len(sent) == 3
    assert not notifications.publish(tmp_path, c, s, l, at)
    assert l.events[-1]['data']['message_id'] == 3
    # Daha önceki BEKLE makbuzu yeni hata durumunu karşılamaz.
    assert not notifications.delivered(l, snapshot('VERİ BEKLENİYOR', 'data_block'))


def test_old_snapshot_cannot_be_sent_as_a_new_days_decision(tmp_path, monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test')
    def must_not_send(*a, **k): raise AssertionError('Eski karar gönderilemez')
    monkeypatch.setattr(notifications.requests, 'post', must_not_send)
    with pytest.raises(ValueError, match='eski'):
        notifications.publish(tmp_path, cfg(), snapshot(), Ledger(tmp_path/'events.jsonl'), NOW+timedelta(days=1))


def test_data_warning_is_a_notification_state_change():
    s = snapshot(); original = notifications.notification_key(s, NOW)
    s['health']['analysis_issues'] = {'AAA': 'Kapanış eski.'}
    assert notifications.notification_key(s, NOW) != original
    s['health']['analysis_issues'] = {}
    assert notifications.notification_key(s, NOW) == original
    s['strategy']['valuation_complete'] = False
    assert notifications.notification_key(s, NOW) != original


@pytest.mark.parametrize('market', ['bist', 'gold'])
def test_daily_close_reports_real_fills_even_if_the_decisions_did_not_change(tmp_path, monkeypatch, market):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test')
    ledger = Ledger(tmp_path/'events.jsonl')
    cfg_market = {**cfg(), 'market': market}
    sent = []

    class Response:
        status_code = 200

        def json(self):
            return {'ok': True, 'result': {'message_id': len(sent)}}

    def post(*args, **kwargs):
        sent.append(kwargs['json']['text'])
        return Response()

    monkeypatch.setattr(notifications.requests, 'post', post)
    s = snapshot()
    s['market'] = market
    assert notifications.publish(tmp_path, cfg_market, s, ledger, NOW)
    ledger.add('fill', 'fill:example', NOW.isoformat(), book='strategy', symbol='AAA',
               side='SELL', price=50., reason='target')
    ledger.add('session_check', 'check:example', NOW.isoformat(), in_execution_window=True,
               expected_quotes=2, valid_quotes=1, decisions=2, errors=[])
    close = NOW.replace(hour=16 if market == 'bist' else 20, minute=17)
    s.update(generated_at=close.isoformat(), analysis_date=NOW.date().isoformat(),
             monitoring={'phase': 'valuation', 'closing_refresh': market == 'bist'})
    s['health'].update(expected_analysis_date=NOW.date().isoformat(), expected_quotes=2, quote_coverage=2)
    assert notifications.publish(tmp_path, cfg_market, s, ledger, close)
    assert 'GÜN SONU' in sent[-1]
    assert '0/1 çalışan işlem çevrimi' in sent[-1]
    assert 'Strateji gerçekleşen: 0 AL, 1 SAT.' in sent[-1]
    assert 'SAT AAA · 50.00 TL · kâr hedefi' in sent[-1]
    assert not notifications.publish(tmp_path, cfg_market, s, ledger, close + timedelta(minutes=2))
    assert ledger.events[-1]['data']['report_day'] == NOW.date().isoformat()
    next_close = close + timedelta(days=1)
    next_day = next_close.date().isoformat()
    s.update(generated_at=next_close.isoformat(), analysis_date=next_day)
    s['health'].update(expected_analysis_date=next_day, quote_coverage=1)
    assert notifications.publish(tmp_path, cfg_market, s, ledger, next_close)
    assert 'Uyarı: kapanış' in sent[-1]
    s['health']['quote_coverage'] = 2
    assert notifications.publish(tmp_path, cfg_market, s, ledger, next_close + timedelta(minutes=2))
    assert 'Uyarı: kapanış' not in sent[-1]
    assert not notifications.publish(tmp_path, cfg_market, s, ledger, next_close + timedelta(minutes=3))


def test_telegram_retries_connect_timeout_without_duplicate_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test')
    sleeps = []
    monkeypatch.setattr(notifications, 'sleep', sleeps.append)

    class Response:
        status_code = 200

        def json(self):
            return {'ok': True, 'result': {'message_id': 123}}

    def post(*args, **kwargs):
        if len(sleeps) < 2:
            raise notifications.requests.ConnectTimeout('secret URL')
        return Response()

    monkeypatch.setattr(notifications.requests, 'post', post)
    ledger = Ledger(tmp_path/'events.jsonl')
    assert notifications.publish(tmp_path, cfg(), snapshot(), ledger, NOW)
    assert sleeps == [1, 2]
    assert [e['data']['message_id'] for e in ledger.events] == [123]


def test_telegram_does_not_resend_during_a_read_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test')
    attempts = []

    def post(*args, **kwargs):
        attempts.append(1)
        raise notifications.requests.ReadTimeout('secret URL')

    monkeypatch.setattr(notifications.requests, 'post', post)
    ledger = Ledger(tmp_path/'events.jsonl')
    with pytest.raises(RuntimeError, match=r'^Telegram teslimi doğrulanamadı \(ReadTimeout\)\.$'):
        notifications.publish(tmp_path, cfg(), snapshot(), ledger, NOW)
    assert len(attempts) == 1 and not ledger.events


def test_watchdog_evidence_counts_persisted_forecasts_and_matches_delivery_time(tmp_path):
    from advisor.watchdog import cycle_evidence

    s = snapshot()
    s['decisions'][0]['forecast_pct'] = 2.5
    s['quotes'] = {'AAA': {'source': 'İş Yatırım'}}
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('forecast', 'forecast:aaa', NOW.isoformat(),
               symbol='AAA', asof=s['analysis_date'])
    ledger.add('notification', 'notification:old', NOW.isoformat(),
               message_id=23, snapshot_at=(NOW - timedelta(hours=1)).isoformat())
    proof = cycle_evidence(s, ledger)
    assert proof['quote_sources'] == ['İş Yatırım']
    assert proof['forecast_symbols'] == proof['archived_forecast_symbols'] == 1
    assert proof['telegram']['message_id'] == 23
    assert proof['telegram']['exact_cycle'] is False


def test_pre_release_valuation_keeps_its_legacy_notification_receipt(tmp_path):
    s = snapshot(now=NOW.replace(hour=16))
    s['analysis_date'] = NOW.date().isoformat()
    s['monitoring'] = {'phase': 'valuation'}
    s['health']['expected_analysis_date'] = s['analysis_date']
    at = datetime.fromisoformat(s['generated_at'])
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('notification', 'notification:legacy', at.isoformat(),
               state_key=notifications.notification_key(s, at), message_id=282, snapshot_at=s['generated_at'])
    assert notifications.delivered(ledger, s, require_closing=False)
    assert not notifications.delivered(ledger, s)


def test_relative_candidate_is_insensitive_to_unmatured_peer_label(monkeypatch):
    from advisor import learning, specialized

    dates = pd.bdate_range('2023-01-02', periods=504).strftime('%Y-%m-%d')
    base = pd.DataFrame({'symbol': 'AAA', 'date': dates, 'label_end': dates,
                         'forward_pct': 1.0, 'quality_ok': True})
    future = base.assign(symbol='BBB', label_end='2030-01-01', forward_pct=1000.)
    for name in learning.ADAPTIVE_FEATURES:
        base[name] = future[name] = 0.

    def fit(rows, *args):
        assert rows.forward_pct.eq(0).all()
        return {'weights': [0], 'features': [], 'mean': [], 'scale': [], 'intercept': 0}

    monkeypatch.setattr(learning, 'fit', fit)
    assert specialized.fit_candidate(pd.concat([base, future]), 'bist', 20, dates[-1])['ready']


def test_history_keeps_the_expected_universe_even_when_a_symbol_has_no_bars():
    con = sqlite3.connect(':memory:')
    con.executescript('CREATE TABLE universe(ticker,sector,in_live);'
                      'CREATE TABLE bars_daily(ticker,date,o,c,c_tr,h,l,v);'
                      "INSERT INTO universe VALUES('AAA','x',1),('BBB','x',1);"
                      "INSERT INTO bars_daily VALUES('AAA','2026-09-21',100,100,100,101,99,1000);")
    f = history.load(con, 'bist', '2026-09-21')
    assert f.attrs['live_symbols'] == ['AAA', 'BBB']
    con.close()


def test_uncertain_split_cannot_publish_current_equity_or_new_buying_power(tmp_path):
    c = cfg(); l = Ledger(tmp_path/'events.jsonl'); fund(l, c, '2026-09-22', NOW.isoformat())
    l.add('fill', 'buy', NOW.isoformat(), book='strategy', symbol='AAA', side='BUY',
          quantity='10', notional_cents=100000, fee_cents=0, stop=90, target=120)
    q = {'bid': 50, 'ask': 50, 'quoted_at': NOW.isoformat()}
    c['blocked_symbols'] = {'AAA': 'Bölünme bilgisi işlemden sonra geldi.'}
    v = policy.value_account(l.account(), {'AAA': q}, c, NOW)
    assert v['equity_try'] is None and v['pnl_try'] is None
    assert 'Bölünme' in v['positions'][0]['valuation_problem']


@pytest.mark.parametrize('reference', [float('nan'), float('inf'), -1, True, '100'])
def test_invalid_gold_reference_blocks_new_entry_without_crashing(reference):
    c = {**cfg(), 'market': 'gold'}
    row = {'symbol': 'GRAM', 'date': '2026-09-21', 'close': 100, 'quality_ok': True,
           'trend50': 2, 'rsi14': 50, 'volatility20': 1}
    q = {'bid': 100, 'ask': 100, 'quoted_at': NOW.isoformat(), 'reference_price': reference}
    d = policy.decision(row, 20, {'ready': True}, c, q, None, None, NOW)
    assert d['action'] == 'VERİ BEKLENİYOR'
    json.dumps(d, allow_nan=False)


def test_future_analysis_cannot_open_a_position():
    row = {'symbol': 'AAA', 'date': '2026-09-23', 'close': 100, 'quality_ok': True,
           'trend50': 2, 'rsi14': 50, 'volatility20': 1}
    q = {'bid': 100, 'ask': 100, 'quoted_at': NOW.isoformat()}
    assert policy.decision(row, 20, {'ready': True}, cfg(), q, None, None, NOW)['action'] == 'VERİ BEKLENİYOR'


def test_forecast_horizon_is_sealed_and_shared_by_shadow_resolution(tmp_path):
    # Ayar değişikliği eski tahmini daha kısa/uzun vadede sonuçlandırmamalı.
    c = cfg(); l = Ledger(tmp_path/'events.jsonl')
    d = {'symbol': 'AAA', 'asof': '2026-09-15', 'action': 'BEKLE',
         'forecast_pct': 10, 'model_id': 'm', 'horizon_sessions': 2}
    outcomes.record(l, [d], {'AAA': 10}, NOW)
    assert l.events[-1]['data']['horizon_sessions'] == 2
    f = pd.DataFrame([{'symbol': 'AAA', 'date': day, 'total_close': price,
                       'forward_pct': 999, 'label_end': '2026-09-16'}
                      for day, price in [('2026-09-15',100), ('2026-09-16',105), ('2026-09-17',110)]])
    l.add('shadow_forecast', 'shadow', NOW.isoformat(), symbol='AAA', asof='2026-09-15',
          horizon_sessions=2, reference_id='r', reference_forecast=8, candidate_forecast=10)
    outcomes.resolve(l, f, c, NOW); shadow.resolve(l, f, NOW)
    result = [e['data'] for e in l.events if e['kind'] in ('forecast_outcome', 'shadow_outcome')]
    assert len(result) == 2
    assert all(r['actual_pct'] == pytest.approx(10) and r['end'] == '2026-09-17' for r in result)
    # İki günlük hata, yirmi günlük modelin düzeltmesini/terfi karnesini besleyemez.
    assert outcomes.calibration(l,c)['resolved_forecasts'] == 0
    assert shadow.score(l,c)['periods'] == 0


def test_changed_horizon_cannot_reinterpret_a_frozen_model_or_disable_its_stop():
    c = {**cfg(), 'horizon_sessions': 10}
    row = {'symbol':'AAA','date':'2026-09-21','close':100,'quality_ok':True,
           'trend50':2,'rsi14':50,'volatility20':1}
    q = {'bid':90,'ask':90,'quoted_at':NOW.isoformat()}
    assert policy.decision(row,20,{'ready':True},c,q,None,None,NOW)['action']=='VERİ BEKLENİYOR'
    held = {'stop':95,'target':120}
    assert policy.decision(row,20,{'ready':True},c,q,held,None,NOW)['code']=='stop'


def test_missing_last_close_blocks_new_buy_but_keeps_existing_stop():
    # 2026-09-22 üretim altını 09-18 analizindeydi; 5 günlük yaş kapısı bunu geçirebiliyordu.
    c = {**cfg(), 'expected_analysis_date': '2026-09-22'}
    row = {'symbol': 'AAA', 'date': '2026-09-21', 'close': 100, 'quality_ok': True,
           'trend50': 2, 'rsi14': 50, 'volatility20': 1}
    q = {'bid': 90, 'ask': 90, 'quoted_at': NOW.isoformat(), 'reference_price': 90}
    model = {'ready': True, 'horizon_sessions': c['horizon_sessions']}
    new = policy.decision(row, 20, model, c, q, None, None, NOW)
    assert new['action'] == 'VERİ BEKLENİYOR'
    assert 'kapanış' in ' '.join(new['reasons'])
    held = policy.decision(row, 20, model, c, q, {'stop': 95, 'target': 120}, None, NOW)
    assert held['code'] == 'stop'


def test_precomputed_label_cannot_bypass_the_sealed_horizon():
    with pytest.raises(ValueError, match='fiyat serisi'):
        outcomes.targets(pd.DataFrame([{'symbol':'AAA','date':'2026-09-15',
                                        'forward_pct':999,'label_end':'2026-09-16'}]),20)


def test_missing_history_stays_in_full_cycle_coverage_and_shadow_stops(tmp_path, monkeypatch):
    from contextlib import contextmanager
    import numpy as np
    from advisor import learning
    c = cfg()
    (tmp_path/'advisor').mkdir(); (tmp_path/'advisor/config.json').write_text(json.dumps(c))
    dates = pd.bdate_range(end='2026-09-21', periods=900).strftime('%Y-%m-%d')
    prices = 100*np.exp(np.arange(900)*.0001)
    f = pd.DataFrame({'symbol':'AAA','date':dates,'close':prices,'total_close':prices,
                      'high':prices*1.01,'low':prices*.99,'volume':1000,'sector':'test','in_live':1})
    f.attrs['live_symbols'] = ['AAA','MISSING']
    con = sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    con.execute('CREATE TABLE corporate_actions(ticker,date,kind,value)')
    @contextmanager
    def connect(*a, **k): yield con
    monkeypatch.setattr(history,'connection',connect)
    monkeypatch.setattr(history,'load',lambda *a:f)
    monkeypatch.setattr(history,'legacy_summary',lambda *a:{'sources':[],'recent':[]})
    monkeypatch.setattr(service.news,'collect',lambda *a,**k:{'items':[],'sources':[]})
    # İki proje aynı motoru sınar; BIST takvim sınıfı yalnız BIST paketinde vardır.
    if (ROOT/'src/calendar_bist.py').exists():
        from src.calendar_bist import BistCalendar
        monkeypatch.setattr(BistCalendar,'__init__',lambda *a:None)
        monkeypatch.setattr(BistCalendar,'last_closed_session',lambda *a:NOW.date()-timedelta(days=1))
    else:
        c['market']='gold'
        (tmp_path/'advisor/config.json').write_text(json.dumps(c))
    def train(f,c,asof):
        m={'ready':True,'id':'test','approved':False,'asof':asof,'weights':[0]*8,
           'mean':[0]*8,'scale':[1]*8,'intercept':0,'evaluation':{},'limitations':[]}
        return m,learning.features(f,20)
    monkeypatch.setattr(learning,'train',train)
    quotes={s:{'bid':100,'ask':100,'quoted_at':NOW.isoformat(),'reference_price':100} for s in ['AAA','MISSING']}
    s=service.cycle(tmp_path,now=NOW,quotes=quotes,offline=True)
    assert s['health']['expected_quotes']==2
    assert next(d for d in s['decisions'] if d['symbol']=='MISSING')['action']=='VERİ BEKLENİYOR'
    assert 'MISSING' in s['health']['analysis_issues']
    # Yalnız gölge hesapta olan varlık da tarihsel evrenden kaybolabilir.
    l=Ledger(tmp_path/'data/advisor/events.jsonl')
    l.add('fill','shadow-owned',(NOW-timedelta(days=1)).isoformat(),book='shadow_reference',
          symbol='SHADOW_ONLY',side='BUY',quantity='1',price=100,notional_cents=10000,fee_cents=0,stop=95,target=120)
    l.save();later=NOW+timedelta(minutes=1)
    q={k:{**v,'quoted_at':later.isoformat()} for k,v in quotes.items()}
    q['SHADOW_ONLY']={'bid':90,'ask':90,'quoted_at':later.isoformat(),'reference_price':90}
    s=service.cycle(tmp_path,now=later,quotes=q,offline=True)
    assert s['health']['expected_quotes']==3
    assert 'SHADOW_ONLY' not in Ledger(l.path).account('shadow_reference')['positions']
    # Aynı 09-21 analizi 09-23'te yeni tahmin gibi karneye sızmamalı.
    held_ledger=Ledger(l.path)
    if 'AAA' not in held_ledger.account()['positions']:
        held_ledger.add('fill','held-AAA',later.isoformat(),book='strategy',symbol='AAA',
                        side='BUY',quantity='1',price=100,notional_cents=10000,fee_cents=0,
                        stop=80,target=120)
        held_ledger.save()
    recorded=[]; original=shadow.record
    def capture(ledger, reference_model, rows, forecasts, now, horizon_sessions):
        recorded.append(rows.copy())
        return original(ledger, reference_model, rows, forecasts, now, horizon_sessions)
    monkeypatch.setattr(shadow,'record',capture)
    stale_now=NOW+timedelta(days=1)
    stale_quotes={k:{**v,'quoted_at':stale_now.isoformat()} for k,v in q.items()}
    stale=service.cycle(tmp_path,now=stale_now,quotes=stale_quotes,offline=True)
    assert recorded and recorded[-1].empty
    assert 'AAA' in stale['health']['analysis_issues']
    assert next(d for d in stale['decisions'] if d['symbol']=='AAA')['code']=='hold'
    assert not [e for e in Ledger(l.path).events if e['kind']=='forecast' and e['at']==stale_now.isoformat()]
    con.close()
