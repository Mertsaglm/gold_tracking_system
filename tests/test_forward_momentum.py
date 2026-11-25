from datetime import datetime, timedelta
from pathlib import Path

from advisor import forward_momentum, service
from advisor.calendar import IST


def test_forward_momentum_waits_for_new_price_and_requires_no_model(tmp_path):
    cfg = service.configuration(Path(__file__).resolve().parents[1])
    cfg.update(market='bist', execution_phase='entry', expected_analysis_date='2026-11-24',
               forward_momentum_start='2026-11-25', blocked_symbols={})
    now = datetime(2026, 11, 25, 11, tzinfo=IST)
    members = [f'T{i:02}' for i in range(30)]
    records = [dict(symbol=s, known_at='2026-11-24', effective_from='2026-11-24',
                    active=True, source='fixture', reason='BIST30') for s in members]
    rows = {s: dict(date='2026-11-24', quality_ok=True, momentum120=i,
                    momentum20=0, volatility20=2, trend50=-10)
            for i, s in enumerate(members)}
    quotes = {s: dict(bid=100, ask=100, quoted_at=now.isoformat()) for s in members}
    first = forward_momentum.cycle(tmp_path, cfg, records, rows, quotes, now, [])
    assert first['strategy']['contributed_try'] == first['benchmark']['contributed_try'] == 50000
    assert not first['strategy']['positions']
    assert first['exposure']['strategy'] == {'invested_pct': 0., 'cash_pct': 100.}
    assert first['risk']['stop_risk_pct'] == 0.
    second_at = now + timedelta(minutes=15)
    for quote in quotes.values():
        quote['quoted_at'] = second_at.isoformat()
    second = forward_momentum.cycle(tmp_path, cfg, records, rows, quotes, second_at, [])
    assert {p['symbol'] for p in second['strategy']['positions']} == set(members[-5:])
    assert second['strategy']['cash_try'] >= 30000
    assert 0 < second['exposure']['strategy']['invested_pct'] <= 40
    assert second['exposure']['strategy']['cash_pct'] > second['exposure']['benchmark']['cash_pct']
    assert 0 < second['risk']['stop_risk_pct'] < 3
    assert second['risk']['stress'][1]['loss_try'] > 0
    assert second['observed_allocation'] == {'days': 1, 'all_cash_days': 0,
                                              'mean_cash_pct': second['exposure']['strategy']['cash_pct']}
    again = forward_momentum.cycle(tmp_path, cfg, records, rows, quotes, second_at, [])
    assert len(again['strategy']['fills']) == 5


def test_allocation_does_not_treat_unknown_marks_as_zero():
    from advisor.reporting import allocation

    assert allocation({'equity_try': None}) == {'invested_pct': None, 'cash_pct': None}
    assert allocation({'equity_try': 100, 'cash_try': 40, 'positions': [{'value_try': 50}]}) == {
        'invested_pct': 50., 'cash_pct': 40.}
