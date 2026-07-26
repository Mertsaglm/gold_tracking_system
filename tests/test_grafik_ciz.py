"""Görsel grafik testleri.

İki şeyi kilitler:

1. **Zarif düşüş.** matplotlib `requirements.txt`'te ama `archive.yml` onu
   kurmuyor. Modülün yokluğu hiçbir akışı düşürmemeli — `ciz()` None döner,
   çağıran devam eder.
2. **Şema kuralı.** Gram TL için OHLC türetilmez (`db.py`); grafik bu kurala
   uymak zorunda. Testler gram panelinin mum değil çizgi olduğunu, mum
   çiziminin YALNIZ gerçek OHLC'si olan ons üzerinde yapıldığını doğrular.

Çizim testleri matplotlib yoksa atlanır (skipif) — CI'da kurulu, yerelde
olmayabilir.
"""
import copy

import pytest

from src import db, grafik_ciz as gc, util

CFG = util.load_config()

try:
    import matplotlib  # noqa: F401
    MPL = True
except ImportError:
    MPL = False


def _cfg(tmp_path):
    c = copy.deepcopy(CFG)
    c["paths"]["db"] = str(tmp_path / "t.sqlite")
    c["paths"]["db_dump"] = str(tmp_path / "t.sql")
    return c


def _doldur(con, n=300):
    from datetime import date, timedelta
    ons_sym = CFG["chart"]["ohlc"]["symbols"]["ons"]
    kur_sym = CFG["chart"]["ohlc"]["symbols"]["kur"]
    d0 = date(2024, 1, 1)
    for i in range(n):
        d = (d0 + timedelta(days=i)).isoformat()
        ons, kur = 2000.0 * (1.0008 ** i), 30.0 * (1.0005 ** i)
        con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                    "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, ons, kur, ons * kur / 31.1035, "test"))
        for sym, p in ((ons_sym, ons), (kur_sym, kur)):
            con.execute("INSERT OR REPLACE INTO ohlc_daily(date,symbol,o,h,l,c,v,"
                        "source) VALUES(?,?,?,?,?,?,?,?)",
                        (d, sym, p * 0.998, p * 1.012, p * 0.988, p, 0, "test"))
    con.commit()


# ---------- saf yardımcılar ----------
def test_sma_penceresi_dolmadan_none():
    m = gc._sma([1.0, 2.0, 3.0, 4.0], 3)
    assert m[0] is None and m[1] is None
    assert m[2] == pytest.approx(2.0) and m[3] == pytest.approx(3.0)


def test_sma_sabit_seride_ayni_deger():
    assert gc._sma([5.0] * 10, 5)[-1] == pytest.approx(5.0)


# ---------- zarif düşüş ----------
def test_matplotlib_yoksa_none_doner_patlamaz(tmp_path, monkeypatch):
    """archive.yml matplotlib kurmuyor; modülün yokluğu akışı düşürmemeli."""
    import builtins
    gercek = builtins.__import__

    def sahte(ad, *a, **k):
        if ad == "matplotlib":
            raise ImportError("test: matplotlib yok")
        return gercek(ad, *a, **k)

    monkeypatch.setattr(builtins, "__import__", sahte)
    assert gc.ciz(_cfg(tmp_path)) is None       # istisna DEĞİL, None


def test_yetersiz_veride_none(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con, n=20)                          # 60 bar eşiğinin altında
    con.close()
    assert gc.ciz(c) is None


# ---------- çizim ----------
@pytest.mark.skipif(not MPL, reason="matplotlib kurulu değil")
def test_png_uretir(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con)
    con.close()
    yol = tmp_path / "g.png"
    sonuc = gc.ciz(c, str(yol))
    assert sonuc and yol.exists()
    assert yol.stat().st_size > 10_000          # boş/bozuk PNG değil
    assert yol.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not MPL, reason="matplotlib kurulu değil")
def test_seviyeler_alinamazsa_yine_cizer(tmp_path, monkeypatch):
    """chart.build_chart patlarsa grafik seviyesiz ama ÇIKAR — rapor deseni."""
    from src import chart
    monkeypatch.setattr(chart, "build_chart",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("test")))
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con)
    con.close()
    assert gc.ciz(c, str(tmp_path / "g.png")) is not None


@pytest.mark.skipif(not MPL, reason="matplotlib kurulu değil")
def test_gram_paneli_mum_cizmez(tmp_path, monkeypatch):
    """ŞEMA KURALI: gram TL için OHLC türetilmez → gram paneli ÇİZGİ olmalı.

    Mum gövdeleri Rectangle olarak eklenir. Ons paneli (gerçek OHLC) çok sayıda
    Rectangle içerir; gram panelinde mum gövdesi OLMAMALI.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    tutulan = {}
    gercek_close = plt.close

    def yakala(fig=None):
        if fig is not None and hasattr(fig, "axes") and len(fig.axes) == 4:
            tutulan["dikdortgen"] = [
                sum(1 for p in ax.patches if isinstance(p, Rectangle))
                for ax in fig.axes]
        return gercek_close(fig)

    monkeypatch.setattr(plt, "close", yakala)
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con, n=300)
    con.close()
    gc.ciz(c, str(tmp_path / "g.png"))

    d = tutulan.get("dikdortgen")
    assert d, "figür yakalanamadı"
    assert d[0] > 100, "ons panelinde mum gövdesi yok"   # gerçek OHLC → mum
    assert d[1] == 0, "gram panelinde mum çizilmiş — şema kuralı ihlali"
