"""DXY yedek kaynağı: FRED ölüyken yfinance devreye girer, kaynak raporda yazılır.

Gerçek durum: FRED (fredgraph.csv) 2026-07-07'den beri üretimde hiç yanıt vermedi
→ panel 7 göstergenin 5'iyle çalışıyordu. Ağ çağrısı yapılmaz; ikisi de monkeypatch'li.
"""
from src import indicators as ind, util
from src.indicators import YOK

CFG = util.load_config()


def _seri(baslangic, bitis, n=30):
    """n günlük düz artan/azalan seri: [(tarih, deger)]."""
    adim = (bitis - baslangic) / (n - 1)
    return [(f"2026-06-{i+1:02d}", baslangic + adim * i) for i in range(n)]


def test_fred_calisiyorsa_yedege_dusmez(monkeypatch):
    monkeypatch.setattr(ind, "_fred_csv", lambda _c, _s: _seri(100.0, 102.0))
    monkeypatch.setattr(ind, "_yf_series",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("yedek çağrılmamalı")))
    sig = ind.dxy_signal(CFG)
    assert sig.label != YOK
    assert "kaynak" not in sig.detail          # FRED'ken kaynak notu yazılmaz


def test_fred_olunce_yfinance_devreye_girer(monkeypatch):
    monkeypatch.setattr(ind, "_fred_csv", lambda _c, _s: None)
    monkeypatch.setattr(ind, "_yf_series", lambda *_a, **_k: _seri(100.0, 102.0))
    sig = ind.dxy_signal(CFG)
    assert sig.label != YOK                   # artık "veri yok" DEĞİL
    assert "DX-Y.NYB" in sig.detail            # hangi kaynak kullanıldı, görünür


def test_ikisi_de_olunce_durust_veri_yok(monkeypatch):
    monkeypatch.setattr(ind, "_fred_csv", lambda _c, _s: None)
    monkeypatch.setattr(ind, "_yf_series", lambda *_a, **_k: None)
    sig = ind.dxy_signal(CFG)
    assert sig.label == YOK


def test_reel_faize_YEDEK_KONULMADI(monkeypatch):
    """Nominal getiri (^TNX) reel faiz yerine geçirilmemeli — kasıtlı tasarım."""
    monkeypatch.setattr(ind, "_fred_csv", lambda _c, _s: None)
    monkeypatch.setattr(ind, "_yf_series",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError(
                            "reel faiz için yedek kaynak KULLANILMAMALI")))
    sig = ind.real_rate_signal(CFG)
    assert sig.label == YOK
    assert "reel" in sig.detail.lower()        # neden yok olduğu yazılı
