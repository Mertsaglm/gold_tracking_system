"""Çekirdek/taktik adaylarında para ve zaman sınırlarının davranış kilitleri."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from advisor import benchmark, corporate, policy, portfolio_candidates as pc, service, universe, filter_diagnostics, news, specialized
from advisor.ledger import Ledger
from scripts.audit_production import independent
from scripts.portfolio_preflight import start_issues
from scripts.portfolio_smoke import run as smoke_run

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 1, 10, 30, tzinfo=timezone.utc)


def config(market='bist'):
    cfg = service.configuration(ROOT)
    cfg.update(market=market, experiment_start_date='2026-10-01',
               execution_phase='entry', expected_analysis_date='2026-09-30',
               blocked_symbols={}, holidays=[], require_next_quote=False,
               core_expected_members=2 if market == 'bist' else 1)
    return cfg


def setup(market='bist', now=NOW):
    symbols = ['AAA', 'BBB'] if market == 'bist' else ['GRAM']
    members = [dict(symbol=s, known_at='2026-09-25', effective_from='2026-09-25',
                    active=True, source='fixture', reason='BIST30') for s in symbols]
    rows = {s: dict(symbol=s, date='2026-09-30', close=100, quality_ok=True,
                    trend50=-1, rsi14=50, volatility20=2, sector=s) for s in symbols}
    quotes = {s: dict(symbol=s, bid=100, ask=100, reference_price=100,
                      quoted_at=now.isoformat(), kind='historical_assumption') for s in symbols}
    return members, rows, quotes


@pytest.mark.parametrize('market', ['bist', 'gold'])
def test_no_signal_funds_core_but_keeps_tactical_cash_and_replay_is_inert(tmp_path, market):
    cfg = config(market)
    members, rows, quotes = setup(market)
    model = {'ready': False, 'horizon_sessions': 20}
    first = pc.cycle(tmp_path, None, cfg, quotes, NOW, members, rows, {}, model)
    accounts = {a['id']: a for a in first['accounts']}
    assert len(accounts['legacy-control']['strategy']['fills']) == 0
    assert {p['sleeve'] for p in accounts['core-cash']['strategy']['positions']} == {'core'}
    assert {p['sleeve'] for p in accounts['core-passive']['strategy']['positions']} == {'core', 'tactical'}
    assert accounts['core-cash']['strategy']['parts']['tactical']['cash_try'] == 10000
    before = {p.parent.name: p.read_bytes() for p in (tmp_path/'portfolio_candidates').glob('*/events.jsonl')}
    pc.cycle(tmp_path, None, cfg, quotes, NOW, members, rows, {}, model)
    assert {p.parent.name: p.read_bytes() for p in (tmp_path/'portfolio_candidates').glob('*/events.jsonl')} == before


def test_bad_or_old_quote_never_fills_any_sleeve(tmp_path):
    members, rows, quotes = setup()
    quotes['AAA']['quoted_at'] = (NOW - timedelta(hours=2)).isoformat()
    quotes['BBB']['bid'] = -1
    out = pc.cycle(tmp_path, None, config(), quotes, NOW, members, rows, {},
                   {'ready': False, 'horizon_sessions': 20})
    for candidate in out['accounts']:
        assert not candidate['strategy']['fills']
        assert candidate['strategy']['cash_try'] == 50000


def test_partial_tactical_sale_cannot_consume_core_lots(tmp_path):
    cfg = config()
    members, rows, quotes = setup()
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('contribution', 'core', NOW.isoformat(), book='core', amount_cents=4000000)
    ledger.add('contribution', 'tactical', NOW.isoformat(), book='tactical', amount_cents=1000000)
    assert pc._trade(ledger, cfg, quotes, NOW, 'core', 'AAA', 'BUY', 10000)['status'] == 'doldu'
    assert pc._trade(ledger, cfg, quotes, NOW, 'tactical', 'AAA', 'BUY', 5000)['status'] == 'doldu'
    original = ledger.account('core')['positions']['AAA']['quantity']
    tactical = ledger.account('tactical')['positions']['AAA']['quantity']
    assert pc._trade(ledger, cfg, quotes, NOW, 'tactical', 'AAA', 'SELL', 2000)['status'] == 'doldu'
    assert ledger.account('core')['positions']['AAA']['quantity'] == original
    assert 0 < ledger.account('tactical')['positions']['AAA']['quantity'] < tactical
    assert ledger.account('core')['cash_cents'] >= 0 and ledger.account('tactical')['cash_cents'] >= 0


def test_same_provider_quote_with_new_observation_time_cannot_fill_twice(tmp_path):
    cfg = config()
    _, _, quotes = setup()
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('contribution', 'cash', NOW.isoformat(), book='core', amount_cents=4000000)
    assert pc._trade(ledger, cfg, quotes, NOW, 'core', 'AAA', 'BUY', 1000)['status'] == 'doldu'
    observed = {**quotes['AAA'], 'observed_at': (NOW+timedelta(minutes=1)).isoformat()}
    assert pc._trade(ledger, cfg, {'AAA':observed}, NOW+timedelta(minutes=1),
                     'core', 'AAA', 'BUY', 1000)['status'] == 'tekrar'
    assert len(ledger.account('core')['fills']) == 1


def test_fractional_slippage_notional_reconciles_to_decimal_lot_times_price(tmp_path):
    # Eski float çarpımı 1000 × 1,050525 için 1050,524999... üretip 1 kuruş eksik yazıyordu.
    cfg = config()
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('contribution', 'cash', NOW.isoformat(), book='tactical', amount_cents=200000)
    q = {'AAA': {'symbol':'AAA', 'bid':1.05, 'ask':1.05,
                 'quoted_at':NOW.isoformat(), 'kind':'historical_assumption'}}
    assert pc._trade(ledger, cfg, q, NOW, 'tactical', 'AAA', 'BUY', 1053)['status'] == 'doldu'
    fill = ledger.account('tactical')['fills'][0]
    assert fill['quantity'] == '1000'
    assert fill['notional_cents'] == 105053


def test_benchmark_pocket_half_cent_reconciles_with_independent_ledger(tmp_path):
    # 2026-09-30 üretim kopyasında TOASO cep alımı float yüzünden 1 kuruş eksik yazılmıştı.
    cfg = config()
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('contribution', 'benchmark:cash', NOW.isoformat(), book='benchmark', amount_cents=105300)
    quote = {'AAA': {'symbol':'AAA', 'bid':1.05, 'ask':1.05,
                     'quoted_at':NOW.isoformat(), 'kind':'historical_assumption'}}
    benchmark.step(ledger, cfg, quote, ['AAA'], NOW)
    fill = ledger.account('benchmark')['fills'][0]
    assert fill['quantity'] == '1000'
    assert fill['notional_cents'] == 105053
    assert independent(ledger.events, 'benchmark')['cash_cents'] == ledger.account('benchmark')['cash_cents']


def test_legacy_mark_rounds_lot_times_price_before_cents():
    cfg = config()
    cfg.update(commission_rate=0, commission_min_try=0,
               commission_bsmv_rate=0, exchange_fee_rate=0, slippage_bps=0)
    account = {'cash_cents':0, 'contributed_cents':105053, 'realized_cents':0,
               'positions':{'AAA':{'quantity':Decimal('1000'),'cost_cents':105053}}, 'fills':[]}
    quote = {'AAA':{'symbol':'AAA','bid':1.050525,'ask':1.050525,
                    'quoted_at':NOW.isoformat(),'kind':'historical_assumption'}}
    assert policy.value_account(account, quote, cfg, NOW)['equity_try'] == 1050.53


def test_dividend_receivable_rounds_fractional_lot_value_once(tmp_path):
    cfg = config()
    cfg.update(start_date='2026-09-25', dividend_tax_rate=0)
    ledger = Ledger(tmp_path/'events.jsonl')
    at = datetime(2026, 9, 29, 10, tzinfo=timezone.utc).isoformat()
    ledger.add('contribution', 'deposit', at, book='strategy', amount_cents=200000)
    ledger.add('fill', 'initial', at, book='strategy', symbol='AAA', side='BUY',
               quantity='1000', price=1.0, notional_cents=100000, fee_cents=0)
    corporate.reconcile(ledger, [{'ticker':'AAA','date':'2026-09-30',
                                  'kind':'temettu','value':1.050525}], cfg, NOW)
    assert ledger.account('strategy')['receivable_cents'] == 105053


def test_external_archive_smoke_cannot_overwrite_account_data():
    # Haricî SQL ile makbuz üretirken yanlış --output canlı defteri ezmemeli.
    with pytest.raises(ValueError, match='veri dizinine'):
        smoke_run(output_override=ROOT/'data/advisor/events.jsonl')


def test_tactical_stop_gap_uses_actual_quote_and_blocks_same_day_reentry(tmp_path):
    cfg = config()
    _, rows, quotes = setup()
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('contribution', 'cash', NOW.isoformat(), book='tactical', amount_cents=1000000)
    assert pc._trade(ledger, cfg, quotes, NOW, 'tactical', 'AAA', 'BUY', 1000, stop=95)['status'] == 'doldu'
    later = NOW + timedelta(minutes=30)
    low = {**quotes['AAA'], 'bid': 80, 'ask': 80, 'quoted_at': later.isoformat()}
    assert pc._trade(ledger, cfg, {'AAA':low}, later, 'tactical', 'AAA', 'SELL', 100000,
                     reason='tactical_stop')['status'] == 'doldu'
    assert ledger.account('tactical')['fills'][-1]['price'] < 95
    assert pc._trade(ledger, cfg, {'AAA':low}, later, 'tactical', 'AAA', 'BUY', 1000)['status'] == 'aynı_gün_satış'


def test_future_membership_cannot_rewrite_earlier_core():
    members, _, _ = setup()
    members += [dict(symbol='CCC', known_at='2026-10-02', effective_from='2026-10-02',
                     active=True, source='fixture', reason='BIST30')]
    assert pc.core_members(members, '2026-10-01', 'bist') == {'AAA', 'BBB'}
    assert pc.core_members(members, '2026-10-02', 'bist') == {'AAA', 'BBB', 'CCC'}


def test_real_october_membership_swap_keeps_core_at_thirty():
    if service.configuration(ROOT)['market'] != 'bist':
        pytest.skip('BIST tarihli üyelik dosyası bu depoda.')
    records = universe.read(ROOT)
    before = pc.core_members(records, '2026-09-30', 'bist')
    after = pc.core_members(records, '2026-10-01', 'bist')
    assert len(before) == len(after) == 30
    assert 'DSTKF' in before and 'DSTKF' not in after
    assert 'TRMET' not in before and 'TRMET' in after
    assert 'CCOLA' not in after and 'CIMSA' not in after


def test_incomplete_bist30_membership_cannot_be_relabelled_as_equal_weight_core(tmp_path):
    members, rows, quotes = setup()
    cfg = config()
    cfg['core_expected_members'] = 30
    out = pc.cycle(tmp_path, None, cfg, quotes, NOW, members, rows, {},
                   {'ready': False, 'horizon_sessions': 20})
    core = next(a for a in out['accounts'] if a['id'] == 'core-cash')
    assert core['strategy']['parts']['core']['fills'] == []
    assert {'status': 'çekirdek_üyeliği_eksik', 'observed': 2, 'expected': 30} in core['diagnostics']


def test_blocked_tactical_sale_remains_due_in_same_week(tmp_path):
    cfg = config()
    cfg['allowed_entry_symbols'] = ['AAA', 'BBB']
    _, rows, quotes = setup()
    ledger = Ledger(tmp_path/'events.jsonl')
    ledger.add('contribution', 'cash', NOW.isoformat(), book='tactical', amount_cents=1000000)
    assert pc._trade(ledger, cfg, quotes, NOW, 'tactical', 'AAA', 'BUY', 1000)['status'] == 'doldu'
    later = NOW + timedelta(minutes=30)
    quotes['AAA']['quoted_at'] = (later - timedelta(hours=2)).isoformat()
    quotes['BBB']['quoted_at'] = later.isoformat()
    actions = pc._tactical(ledger, cfg, rows, quotes, {'BBB': 0}, {'BBB': 0}, later)
    assert any(a['status'] == 'veri_engeli' and a['symbol'] == 'AAA' for a in actions)
    assert not any(e['kind'] == 'rebalance_check' for e in ledger.events)
    assert pc._week('2027-01-01') == '2026-W53'


def test_tactical_gold_risk_budget_is_observed(tmp_path):
    cfg = config('gold')
    members, rows, quotes = setup('gold')
    out = pc.cycle(tmp_path, None, cfg, quotes, NOW, members, rows, {'GRAM': 20},
                   {'ready': False, 'horizon_sessions': 20})
    tactical = next(a for a in out['accounts'] if a['id'] == 'core-ridge')['strategy']['parts']['tactical']
    if tactical['positions']:
        p = tactical['positions'][0]
        loss_at_stop = float(p['quantity']) * (quotes['GRAM']['ask'] - p['stop'])
        assert loss_at_stop <= 500 + 1
        assert p['value_try'] <= 10000 + 1


def test_filter_interaction_uses_only_fully_measured_denominator():
    checks = lambda values: [{'check': name, 'status': status} for name, status in values.items()]
    rows = [{'code': 'reward_risk', 'checks': checks({'maliyet':'geçti','trend':'geçti',
              'rsi':'geçti','kazanc_risk':'kaldı'})},
            {'code': 'data_block', 'checks': checks({'veri':'kaldı','maliyet':'değerlendirilmedi',
              'trend':'değerlendirilmedi','rsi':'değerlendirilmedi','kazanc_risk':'değerlendirilmedi'})}]
    result = filter_diagnostics.summarize(rows)
    assert result['decisions'] == 2
    assert result['bist_interaction']['fully_evaluated'] == 1
    assert result['bist_interaction']['without_rr'] == 1
    assert result['gates']['maliyet']['not_evaluated'] == 1


def test_news_first_seen_is_forward_only_and_repeated_sync_does_not_rewrite_it(tmp_path):
    ledger = Ledger(tmp_path/'events.jsonl')
    item = {'source':'KAP','url':'https://kap.org.tr/test','published_at':'2026-09-01T07:00:00+00:00',
            'asset':'AAA','event_type':'ODA','title':'fixture'}
    first = {'items':[dict(item)]}
    news.attach_first_seen(ledger, first, NOW)
    later = {'items':[dict(item)]}
    news.attach_first_seen(ledger, later, NOW+timedelta(days=1))
    assert first['items'][0]['first_seen_at'] == later['items'][0]['first_seen_at'] == NOW.isoformat()
    assert len([e for e in ledger.events if e['kind']=='news_seen']) == 1


def test_specialized_training_fingerprint_ignores_later_labels_but_sees_revisions():
    import pandas as pd
    frame = pd.DataFrame({'symbol':['AAA','AAA','AAA'],
                          'date':['2026-09-01','2026-09-02','2026-09-03'],
                          'close':[100,101,102], 'total_close':[100,101,102],
                          'forward_pct':[1,2,3]})
    original = specialized._causal_input_id(frame, '2026-09-02')
    later = frame.copy();later.loc[0,'forward_pct'] = 999;later.loc[2,'close'] = 999
    assert specialized._causal_input_id(later, '2026-09-02') == original
    later.loc[1,'close'] = 99
    assert specialized._causal_input_id(later, '2026-09-02') != original


def test_preflight_rejects_backdated_or_closed_t0():
    calendar = {'available':True, 'years':['2026'], 'full_days':['2026-10-05']}
    cfg = {'calendar':calendar}
    today = date(2026, 10, 1)
    assert start_issues(None, today, cfg)
    assert start_issues('2026-10-01', today, cfg)
    assert start_issues('2026-10-03', today, cfg)
    assert start_issues('2026-10-05', today, cfg)
    assert start_issues('2026-10-06', today, cfg) == []
