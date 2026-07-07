"""Sinyal motoru saf fonksiyon testleri."""
from src import signals


def test_atr_proxy_constant_series_zero():
    # sabit fiyat -> ATR 0
    assert signals.atr_proxy([100.0] * 20) == 0.0


def test_atr_proxy_known():
    # her gün +10 -> |Δ|=10 -> ATR=10
    prices = [100 + 10 * i for i in range(20)]
    assert signals.atr_proxy(prices, window=14) == 10.0


def test_atr_proxy_insufficient():
    assert signals.atr_proxy([1, 2, 3], window=14) is None


def test_signal_schema_shape():
    s = signals._signal("test", "alim", ["birikimci"], ["gerekçe"], "orta",
                        "geçersizlik koşulu", "1 ay")
    for k in ("sinyal", "yon", "profil", "gerekce", "guven", "gecersizlik",
              "ufuk", "backtest", "uyari"):
        assert k in s
    assert s["backtest"] == "tarihsel doğrulaması yok"   # varsayılan
    assert "yatırım tavsiyesi değildir" in s["uyari"]


def test_format_signals_md_empty():
    out = signals.format_signals_md({"signals": []})
    assert "Sinyaller" in out
