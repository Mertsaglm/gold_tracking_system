"""2026-11-17 üretim görünümü: değerleme ve karar tanısı aynı kapıyı kullanır."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from advisor import engine
from advisor.ledger import Ledger, fund
from tests.advisor_legacy import legacy_configuration


@pytest.mark.parametrize('stale', [False, True])
def test_valuation_trace_matches_engine_without_enabling_fills(tmp_path, stale):
    cfg = legacy_configuration(Path(__file__).resolve().parents[1])
    cfg.update(market='bist', execution_phase='valuation', expected_analysis_date='2026-11-17')
    now = datetime(2026, 11, 17, 16, 58, tzinfo=timezone.utc)
    ledger = Ledger(tmp_path/'events.jsonl')
    fund(ledger, cfg, '2026-11-17', now.isoformat())
    row = dict(symbol='AAA', date='2026-11-17', close=100, quality_ok=True,
               trend50=-5, rsi14=50, volatility20=1)
    quote = dict(symbol='AAA', bid=100, ask=100,
                 quoted_at=(now-timedelta(hours=2) if stale else now).isoformat())
    decisions, fills = engine.run(ledger, [row], {'AAA':20}, {'ready':True}, cfg, {'AAA':quote}, now)
    decision, = decisions
    assert fills == []
    assert decision['action'] != 'AL'
    data = next(c for c in decision['checks'] if c['check']=='veri')
    assert data['status'] == ('kaldı' if stale else 'geçti')
    if not stale:
        assert decision['code'] == 'no_edge'
        assert next(c for c in decision['checks'] if c['check']=='trend')['status'] == 'kaldı'
