"""Backtest çekirdek fonksiyonları — sentetik seriyle bilinen girdi → bilinen çıktı."""
import math

from src import backtest as bt


def test_dist_stats_known():
    r = [10, -5, 20, 0, 15]
    s = bt.dist_stats(r, weak_n=3)
    assert s["n"] == 5
    assert not s["weak"]
    assert s["medyan"] == 10
    assert s["en_kotu"] == -5
    assert s["en_iyi"] == 20
    assert math.isclose(s["kazanma_pct"], 60.0)   # 3/5 pozitif


def test_dist_stats_weak_flag():
    s = bt.dist_stats([1, 2], weak_n=15)
    assert s["weak"] is True


def test_dist_stats_empty():
    assert bt.dist_stats([])["n"] == 0


def test_forward_returns_lookahead():
    # fiyat her gün +%10 birikimli: 100,110,121,133.1,146.41
    prices = [100, 110, 121, 133.1, 146.41]
    dates = [f"d{i}" for i in range(5)]
    # sinyal gün 0 -> giriş gün1(110), çıkış gün1+2=gün3(133.1) -> %21
    r = bt.forward_returns(dates, prices, [0], horizon=2)
    assert len(r) == 1
    assert math.isclose(r[0], 21.0, rel_tol=1e-6)


def test_forward_returns_boundary_skipped():
    prices = [100, 110, 121]
    # sinyal gün 1: giriş gün2, çıkış gün2+2=gün4 -> sınır dışı, atlanır
    r = bt.forward_returns(["a", "b", "c"], prices, [1], horizon=2)
    assert r == []


def test_regime_labels():
    thr = 20.0
    # A: ustunde, reel faiz dusuyor, dusuk vol
    assert bt.regime_label(110, 100, -0.2, 10, thr) == "A"
    # B: ustunde, reel faiz dusuyor, yuksek vol
    assert bt.regime_label(110, 100, -0.2, 30, thr) == "B"
    # C: altinda, reel faiz yukseliyor
    assert bt.regime_label(90, 100, +0.2, 10, thr) == "C"
    # D: ustunde ama reel faiz yukseliyor (anomali)
    assert bt.regime_label(110, 100, +0.2, 10, thr) == "D"
    # X: veri eksik
    assert bt.regime_label(110, None, -0.2, 10, thr) == "X"


def test_dca_simulate_basic():
    # 3 ay, fiyat sabit 100, ayda 1000 TL -> 30 gram, deger 3000, getiri 0
    mk = ["2020-01-01", "2020-02-01", "2020-03-01"]
    mp = {d: 100 for d in mk}
    r = bt.dca_simulate(mk, mp, 1000)
    assert math.isclose(r.yatirilan, 3000)
    assert math.isclose(r.birim, 30)
    assert math.isclose(r.getiri_pct, 0.0)


def test_dca_condition_filters():
    mk = ["2020-01-01", "2020-02-01", "2020-03-01"]
    mp = {d: 100 for d in mk}
    # sadece ocak ayinda al
    r = bt.dca_simulate(mk, mp, 1000, buy_condition=lambda d: d == "2020-01-01")
    assert math.isclose(r.yatirilan, 1000)
    assert math.isclose(r.birim, 10)


def test_dca_price_rise_gain():
    mk = ["2020-01-01", "2020-02-01"]
    mp = {"2020-01-01": 100, "2020-02-01": 200}
    r = bt.dca_simulate(mk, mp, 1000)
    # ocak: 10 gram; subat: 5 gram -> 15 gram × 200 = 3000; yatirilan 2000 -> +50%
    assert math.isclose(r.birim, 15)
    assert math.isclose(r.getiri_pct, 50.0)


def test_deposit_simulate_compounds():
    mk = ["2020-01-01", "2020-02-01", "2020-03-01"]
    rates = {d: 12.0 for d in mk}   # yıllık %12 brüt
    r = bt.deposit_simulate(mk, rates, 1000, stopaj_pct=0.0)
    # net aylik = 1% ; bakiye: ay1 1000, ay2 1000*1.01+1000, ay3 (...)*1.01+1000
    assert r.deger > 3000            # faiz eklendi
    assert math.isclose(r.yatirilan, 3000)


def test_max_drawdown():
    assert math.isclose(bt._max_drawdown([100, 120, 60, 90]), -50.0, rel_tol=1e-9)
    assert bt._max_drawdown([100, 110, 120]) == 0.0
