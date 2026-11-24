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
    second_at = now + timedelta(minutes=15)
    for quote in quotes.values():
        quote['quoted_at'] = second_at.isoformat()
    second = forward_momentum.cycle(tmp_path, cfg, records, rows, quotes, second_at, [])
    assert {p['symbol'] for p in second['strategy']['positions']} == set(members[-5:])
    assert second['strategy']['cash_try'] >= 30000
    again = forward_momentum.cycle(tmp_path, cfg, records, rows, quotes, second_at, [])
    assert len(again['strategy']['fills']) == 5
