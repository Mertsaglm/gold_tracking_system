"""Hesaplayıcı birim testleri (config'ten sabitlerle, bilinen girdi → çıktı)."""
import math

from src import calculators as clc
from src import util

CFG = util.load_config()


def test_fiziki_gram_spread():
    # sıfır getiri, %3 makas -> net %-3
    r = clc.instrument_net(CFG, "fiziki_gram", 100000, 12, annual_gold_pct=0.0)
    assert math.isclose(r["net_getiri_pct"], -3.0, abs_tol=1e-6)


def test_altin_fonu_stopaj_on_gain():
    # %100 brüt getiri, %15 stopaj, yönetim ücreti düş
    r = clc.instrument_net(CFG, "altin_fonu", 100000, 12, annual_gold_pct=100.0)
    # kazanç stopajla kısılmış olmalı -> net getiri < %100
    assert r["net_getiri_pct"] < 100.0
    assert r["net_getiri_pct"] > 0


def test_banka_hesap_costs():
    # sıfır getiri: iki makas + BSMV -> net negatif
    r = clc.instrument_net(CFG, "banka_hesap", 100000, 12, annual_gold_pct=0.0)
    assert r["net_getiri_pct"] < 0


def test_compare_sorts_by_net():
    res = clc.compare_instruments(CFG, 100000, 12, annual_gold_pct=30.0)
    nets = [s["net"] for s in res["sonuclar"]]
    assert nets == sorted(nets, reverse=True)
    assert res["kazanan"] == res["sonuclar"][0]["enstruman"]


def test_break_even_returns_month_or_none():
    be = clc.break_even_month(CFG, 100000, annual_gold_pct=30.0)
    assert be is None or (1 <= be <= 120)


def test_bilezik_basabas_known():
    # 10g, %0 işçilik -> başabaş %0; hurda = 10*0.916*6000
    r = clc.bilezik_basabas(CFG, 10.0, 0.0, 6000.0)
    assert math.isclose(r["hurda_deger"], 10 * 0.916 * 6000)
    assert math.isclose(r["basabas_gereken_gram_yukselis_pct"], 0.0, abs_tol=1e-9)


def test_bilezik_labor_burns():
    # %25 işçilik -> başabaş için gram +%25 gerekir
    r = clc.bilezik_basabas(CFG, 20.0, 25.0, 6200.0)
    assert math.isclose(r["basabas_gereken_gram_yukselis_pct"], 25.0, abs_tol=1e-9)
    assert r["odenen_toplam"] > r["hurda_deger"]
