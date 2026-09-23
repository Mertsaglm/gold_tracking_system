"""V2 regresyonları: para korunumu, fiyat yönü, kronoloji ve gerçek karar yolu."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from advisor import learning, marketdata, policy, service
from advisor.ledger import Ledger, cents, fund

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)


@pytest.fixture
def advisor_cfg():
    c = service.configuration(ROOT)
    c.update(market="bist", max_position_pct=20, max_positions=5, initial_try=5000, monthly_try=5000)
    return c


def quote(price=100, spread=0):
    return {"symbol": "AAA", "bid": price, "ask": price * (1 + spread),
            "quoted_at": NOW.isoformat(), "observed_at": NOW.isoformat(), "source": "fixture"}


def buy(symbol="AAA"):
    return {"symbol": symbol, "action": "AL", "code": "test", "price": 100,
            "stop": 95, "target": 115, "deadline": "2026-10-15", "forecast_pct": 15,
            "confidence": "orta", "key": "decision:test", "reasons": ["Test"]}


def test_contributions_idempotent_and_month_rollover(tmp_path, advisor_cfg):
    l = Ledger(tmp_path / "events.jsonl")
    fund(l, advisor_cfg, "2026-09-15", NOW.isoformat())
    fund(l, advisor_cfg, "2026-09-15", NOW.isoformat())
    assert l.account()["cash_cents"] == 500000
    fund(l, advisor_cfg, "2027-01-01", NOW.isoformat())
    assert l.account()["cash_cents"] == 2500000
    assert l.account("benchmark")["cash_cents"] == 2500000


def test_closed_session_exits_before_history_model_or_trades(tmp_path, monkeypatch):
    """Mesai dışı workflow_run eski sürümlerde tam hesaplama yapıyordu."""
    cfg = service.configuration(ROOT)
    (tmp_path / "advisor").mkdir()
    (tmp_path / "advisor/config.json").write_text(json.dumps(cfg))

    def history_must_not_open(*args, **kwargs):
        raise AssertionError("Mesai dışı koşu veritabanını açmamalı.")

    monkeypatch.setattr(service.history, "connection", history_must_not_open)
    night = datetime(2026, 9, 15, 20, 0, tzinfo=timezone.utc)
    result = service.cycle(tmp_path, now=night, offline=True)

    assert result["skipped"] is True
    assert "İşlem penceresi dışında" in result["skip_reason"]
    ledger = Ledger(tmp_path / "data/advisor/events.jsonl")
    assert [event["kind"] for event in ledger.events] == ["session_check"]
    assert ledger.events[0]["data"]["in_execution_window"] is False
    assert not (tmp_path / "data/advisor/latest.json").exists()


def test_hash_chain_catches_modified_history(tmp_path, advisor_cfg):
    p = tmp_path / "events.jsonl"
    l = Ledger(p)
    fund(l, advisor_cfg, "2026-09-15", NOW.isoformat())
    l.save()
    p.write_text(p.read_text().replace('500000', '600000', 1))
    with pytest.raises(ValueError, match="bütünlüğü"):
        Ledger(p)


@pytest.mark.parametrize("budget", [1, 20, 99, 100, 101, 499, 10000, 500000])
def test_lot_rounding_never_overspends(budget, advisor_cfg):
    qty = policy.quantity_for(budget, 49.37, advisor_cfg)
    assert qty % 1 == 0
    assert cents(float(qty) * 49.37) + policy.fee(advisor_cfg, float(qty) * 49.37, "BUY") <= budget


def test_bank_gold_uses_ask_buy_bid_sell_and_tax(tmp_path, advisor_cfg):
    c = {**advisor_cfg, "market": "gold", "max_position_pct": 100, "minimum_cash_pct": 0, "risk_per_trade_pct": 2}
    q = quote(6000, 0.02)
    assert policy.execution_price(q, c, "BUY") == 6120
    assert policy.execution_price(q, c, "SELL") == 6000
    assert policy.fee(c, 1000, "BUY") == 200
    assert policy.fee(c, 1000, "SELL") == 0
    qty = policy.quantity_for(500000, 6120, c)
    assert qty == Decimal("0.81")


def test_fills_idempotent_cash_conserved_and_no_same_day_reentry(tmp_path, advisor_cfg):
    l = Ledger(tmp_path / "ledger.jsonl")
    fund(l, advisor_cfg, "2026-09-15", NOW.isoformat())
    fills = policy.execute(l, advisor_cfg, [buy()], {"AAA": quote()}, NOW)
    assert len(fills) == 1
    assert policy.execute(l, advisor_cfg, [buy()], {"AAA": quote()}, NOW) == []
    a = l.account()
    assert a["cash_cents"] + a["positions"]["AAA"]["cost_cents"] == 500000
    sell = {**buy(), "action": "SAT", "code": "stop"}
    policy.execute(l, advisor_cfg, [sell], {"AAA": quote(98)}, NOW)
    assert not l.account()["positions"]
    assert l.account()["cash_cents"] < 500000
    assert not policy.execute(l, advisor_cfg, [buy()], {"AAA": quote()}, NOW + timedelta(hours=1))
    l.save()
    assert Ledger(l.path).account() == l.account()


@pytest.mark.parametrize("delta", [-120, 30])
def test_stale_or_future_quote_cannot_fill(tmp_path, advisor_cfg, delta):
    l = Ledger(tmp_path / "ledger.jsonl")
    fund(l, advisor_cfg, "2026-09-15", NOW.isoformat())
    q = quote()
    q["quoted_at"] = (NOW + timedelta(minutes=delta)).isoformat()
    assert not policy.execute(l, advisor_cfg, [buy()], {"AAA": q}, NOW)
    assert l.account()["cash_cents"] == 500000


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 0])
def test_non_finite_quotes_rejected(advisor_cfg, bad):
    assert marketdata.usable(quote(bad), advisor_cfg, NOW)


def test_quote_parser_chooses_bank_not_generic_gold():
    html = 'İş Bankası Gram Altın <span data-socket-key="gram-altin" data-socket-attr="ask">999,00</span>'
    for attr, val in [("bid", "6.575,00"), ("ask", "6.755,59"), ("ts", "13:25")]:
        html += f'<span data-socket-key="4-gram-altin" data-socket-attr="{attr}">{val}</span>'
    q = marketdata.parse_gold(html, NOW, "https://example.test")["GRAM"]
    assert q["bid"] == 6575 and q["ask"] == 6755.59
    assert q["timestamp_kind"] == "time_only"


def test_stock_parser_requires_page_date():
    html = '<div id="allStockTable"><table><tr><td><a href="sirket-karti.aspx?hisse=AAA">AAA</a></td><td>101,50</td></tr></table></div>'
    with pytest.raises(ValueError, match="damgası"):
        marketdata.parse_stocks(html, NOW, "url", ["AAA"])
    html += '<!-- önbellek profili kullanılarak işlendi, saat: 2026-09-15T13:25:00 -->'
    assert marketdata.parse_stocks(html, NOW, "url", ["AAA"])["AAA"]["ask"] == 101.5


def series(n=1000):
    days = pd.bdate_range("2020-01-01", periods=n).strftime("%Y-%m-%d")
    close = 100 * np.exp(np.arange(n) * 0.0003 + 0.08 * np.sin(np.arange(n) / 37))
    return pd.DataFrame({"symbol": "AAA", "date": days, "close": close, "total_close": close,
                         "high": close * 1.01, "low": close * .99, "volume": 1000, "sector": "test", "in_live": 1})


def test_features_cannot_read_future():
    f = series()
    cut = f.iloc[700].date
    before = learning.features(f[f.date <= cut], 20).iloc[-1]
    f.loc[f.date > cut, "total_close"] *= 100
    after = learning.features(f, 20).loc[lambda x: x.date == cut].iloc[0]
    np.testing.assert_allclose(before[learning.FEATURES].to_numpy(float), after[learning.FEATURES].to_numpy(float))


def test_model_walk_forward_purges_unmatured_labels(advisor_cfg):
    f = series()
    c = copy.deepcopy(advisor_cfg)
    c["learning"]["min_training_dates"] = 252
    m, _ = learning.train(f, c, f.iloc[-1].date)
    assert m["ready"] and m["folds"]
    assert all(x["train_label_end"] < x["test_start"] for x in m["folds"])
    assert m["label_end"] <= f.iloc[-1].date
    periods = m["evaluation"]["series"]
    assert all(a["end"] <= b["date"] for a, b in zip(periods, periods[1:]))


def test_model_asof_unaffected_by_later_data(advisor_cfg):
    f = series()
    cut = f.iloc[850].date
    a, _ = learning.train(f, advisor_cfg, cut)
    f.loc[f.date > cut, "total_close"] *= 100
    b, _ = learning.train(f, advisor_cfg, cut)
    assert a["id"] == b["id"]


def test_missing_mark_does_not_value_position_at_zero(tmp_path, advisor_cfg):
    l = Ledger(tmp_path / "x.jsonl")
    fund(l, advisor_cfg, "2026-09-15", NOW.isoformat())
    policy.execute(l, advisor_cfg, [buy()], {"AAA": quote()}, NOW)
    value = policy.value_account(l.account(), {}, advisor_cfg)
    assert value["equity_try"] is None and not value["valuation_complete"]


def test_deposit_is_not_investment_profit(tmp_path):
    l = Ledger(tmp_path / "x.jsonl")
    l.add("valuation", "v1", NOW.isoformat(), equity_try=5000, contributed_try=5000, nav=1)
    result = service.feedback(l, {"equity_try": 10000, "contributed_try": 10000, "fills": []})
    assert result["twr_pct"] == 0


def test_no_imaginary_reward_target_to_pass_gate(advisor_cfg):
    row = {"symbol": "AAA", "date": "2026-09-14", "close": 100, "quality_ok": True, "trend50": 5, "rsi14": 55, "volatility20": 2}
    d = policy.decision(row, 2.5, {"ready": True, "approved": True}, advisor_cfg, quote(), None, None, NOW)
    assert d["action"] == "BEKLE" and d["code"] == "reward_risk"
    assert d["target"] < 103


def test_gold_not_forced_to_sell_every_month(advisor_cfg):
    c = {**advisor_cfg, "market": "gold"}
    row = {"symbol": "GRAM", "date": "2026-09-14", "quality_ok": True, "trend50": 5, "rsi14": 55, "volatility20": 2}
    position = {"stop": 90, "target": 120, "deadline": "2026-09-01"}
    assert policy.decision(row, 5, {"ready": True}, c, quote(), position, None, NOW)["action"] == "TUT"
