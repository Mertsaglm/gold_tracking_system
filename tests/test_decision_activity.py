from datetime import date, datetime
from pathlib import Path

import pytest

from advisor.ledger import Ledger
from advisor.decision_activity import measure
from advisor.reporting import weekly_research


def config():
    return {'market': 'gold', 'max_spread_pct': 3, 'max_quote_age_minutes': 25,
            'gold_buy_tax_rate': 0.002, 'entry_intent_minutes': 90,
            'execution_window': {'open': '09:00', 'close': '23:00'},
            'entry_window': {'open': '09:00', 'close': '18:00'},
            'observation_window': {'open': '09:00', 'close': '23:30'}}


def quote(ledger, key, at, bid, ask, *, quoted_at=None):
    ledger.add('quote_snapshot', key, at, quotes={'GRAM': {
        'bid': bid, 'ask': ask, 'quoted_at': quoted_at or at,
    }})


def waiting(ledger, key, at):
    ledger.add('decision', key, at, symbol='GRAM', asof='2026-11-19', action='BEKLE',
               code='spread_limit', prediction={'raw_pct': 2, 'horizon_sessions': 1})


def test_waiting_outcomes_use_next_quote_bank_sides_and_matched_passive_nav(tmp_path):
    ledger = Ledger(tmp_path / 'events.jsonl')
    signal, entry, exit_time = ('2026-11-20T09:15:00+03:00', '2026-11-20T09:45:00+03:00',
                                '2026-11-23T09:15:00+03:00')
    quote(ledger, 'before', signal, 95, 100)
    waiting(ledger, 'first', signal)
    waiting(ledger, 'same-day', '2026-11-20T09:30:00+03:00')
    quote(ledger, 'entry', entry, 95, 100)
    ledger.add('valuation', 'entry-nav', entry, benchmark_nav=1.00)
    quote(ledger, 'exit', exit_time, 105, 120)
    ledger.add('valuation', 'exit-nav', exit_time, benchmark_nav=1.02)
    result = measure(ledger, config(), start='2026-11-20', through='2026-11-23',
                     budget=100_000, corporate_days={})
    row, = result['outcomes']
    assert row['decision_key'] == 'first'
    assert row['maturity'] == '2026-11-23'
    assert row['entry_at'] == entry
    assert row['net_pct'] == pytest.approx(4.79)
    assert row['excess_pct'] == pytest.approx(2.79)
    assert result['outcomes_by_code']['spread_limit']['beat_passive'] == 1
    assert result['entry_diagnostics']['decisions'] == 2
    assert result['fills'] == []
    assert not ledger.path.exists()


def test_pending_stale_and_corporate_action_are_visible_in_denominator(tmp_path):
    ledger = Ledger(tmp_path / 'events.jsonl')
    signal = '2026-11-20T09:15:00+03:00'
    quote(ledger, 'before', signal, 95, 100)
    waiting(ledger, 'first', signal)
    quote(ledger, 'unchanged-stamp', '2026-11-20T09:25:00+03:00', 96, 101, quoted_at=signal)
    quote(ledger, 'exit', '2026-11-23T09:15:00+03:00', 104, 110)

    def run(through, actions=None):
        result = measure(ledger, config(), start='2026-11-20', through=through,
                         budget=100_000, corporate_days=actions or {})
        return result['outcomes_by_code']['spread_limit']

    assert run('2026-11-20')['statuses'] == {'pending': 1}
    summary = run('2026-11-23')
    assert summary['statuses'] == {'no_entry_quote': 1}
    assert summary['mean_net_pct'] is None
    assert run('2026-11-23', {'GRAM': [date(2026, 11, 23)]})['statuses'] == {'corporate_action': 1}


def test_weekly_research_uses_maturity_week_and_economic_denominators(tmp_path):
    ledger = Ledger(tmp_path / 'events.jsonl')
    for day in ('2026-11-13', '2026-11-20'):
        signal = day + 'T09:15:00+03:00'
        quote(ledger, day, signal, 95, 100)
        waiting(ledger, day + '-decision', signal)
        quote(ledger, day + '-entry', day + 'T09:45:00+03:00', 95, 100)
    quote(ledger, 'old-exit', '2026-11-16T09:15:00+03:00', 120, 125)
    quote(ledger, 'latest-exit', '2026-11-23T09:15:00+03:00', 90, 95)
    config_with_start = {**config(), 'start_date':'2026-09-25'}
    lines = weekly_research(Path(__file__).resolve().parents[1], tmp_path, ledger, config_with_start,
                            datetime.fromisoformat('2026-11-24T19:00:00+03:00'))
    assert any('ölçülen 1/1' in line and 'nakit üstü 0/1' in line for line in lines)
    assert any('ortalaması nakdi geçmedi' in line for line in lines)
    assert not ledger.path.exists()
