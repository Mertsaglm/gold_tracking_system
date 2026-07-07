"""Hesap katmanı birim testleri."""
import math

import pytest

from src import calc


def test_theoretical_gram():
    # ons 4128$, kur 46.84 -> teorik gram
    t = calc.theoretical_gram(4128.0, 46.84)
    assert math.isclose(t, 4128.0 / 31.1034768 * 46.84, rel_tol=1e-9)


def test_purity_adjustment_half_percent():
    """Saflık düzeltmesi ~%0.5 fark yaratmalı (gram-altin vs gram-has-altin)."""
    theoretical = 6216.90
    gram_has = 6216.90            # has, düzeltmeli
    gram_retail = 6248.14         # perakende, ~%0.5 üstte
    prim_adj = calc.prim_pct(gram_has, theoretical)
    prim_naive = calc.prim_pct(gram_retail, theoretical)
    diff = prim_naive - prim_adj
    assert 0.4 <= diff <= 0.6, f"saflık farkı ~0.5 bekleniyordu, {diff:.3f} çıktı"


def test_spread_pct():
    s = calc.spread_pct(6215.93, 6216.90)
    assert s > 0
    mid = (6215.93 + 6216.90) / 2
    assert math.isclose(s, (6216.90 - 6215.93) / mid * 100, rel_tol=1e-9)


def test_quarter_prim_has_content():
    """Çeyrek has içeriği = 1.804 * 0.916; fair fiyat buna göre."""
    gram_has = 6216.90
    # tam adil (primsiz) çeyrek: has_content * gram_has
    has_content = 1.804 * 0.916
    fair = has_content * gram_has
    qp0 = calc.quarter_prim_pct(fair, gram_has, 1.804, 0.916)
    assert math.isclose(qp0, 0.0, abs_tol=1e-9)
    # gerçek çeyrek satış 10249.98 -> makul bandda (işçilik/likidite ±%5)
    qp = calc.quarter_prim_pct(10249.98, gram_has, 1.804, 0.916)
    assert -5.0 < qp < 5.0
    # fiyat artışı primi artırır (monotonluk)
    assert calc.quarter_prim_pct(10500.0, gram_has, 1.804, 0.916) > qp


def test_decompose_sums_exactly():
    """Bileşenler toplamı total'a tam eşit olmalı."""
    d = calc.decompose(4100, 46.5, 0.2, 4150, 46.9, 0.5)
    assert math.isclose(d.ons_pct + d.kur_pct + d.prim_pct, d.total_pct, rel_tol=1e-12)


def test_decompose_matches_gram_logreturn():
    """total_pct == ln(gram1/gram0)*100 (gram = teorik*(1+prim))."""
    ons0, usd0, p0 = 4100, 46.5, 0.2
    ons1, usd1, p1 = 4150, 46.9, 0.5
    g0 = calc.gram_from_theoretical(calc.theoretical_gram(ons0, usd0), p0)
    g1 = calc.gram_from_theoretical(calc.theoretical_gram(ons1, usd1), p1)
    expected = math.log(g1 / g0) * 100
    d = calc.decompose(ons0, usd0, p0, ons1, usd1, p1)
    assert math.isclose(d.total_pct, expected, rel_tol=1e-10)


def test_zscore_insufficient():
    z = calc.zscore([1.0, 2.0, 3.0], 2.0, min_samples=60)
    assert z.status == "insufficient"
    assert z.value is None
    assert z.n == 3


def test_zscore_ok():
    hist = [float(i % 5) for i in range(100)]
    z = calc.zscore(hist, 10.0, min_samples=60)
    assert z.status == "ok"
    assert z.value is not None
    assert z.n == 100


def test_zscore_flat():
    z = calc.zscore([2.0] * 80, 2.0, min_samples=60)
    assert z.status == "flat"
