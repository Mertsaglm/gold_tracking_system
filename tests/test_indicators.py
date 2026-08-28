"""Kadran paneli etiketleme mantığı testleri (saf fonksiyonlar)."""
from src import indicators as ind, util
from src.indicators import Signal, OLUMLU, NOTR, OLUMSUZ, YOK


def test_real_rate_falling_is_positive():
    assert ind.label_real_rate(-10.0, 5.0) == OLUMLU     # 10bps düşüş
    assert ind.label_real_rate(+10.0, 5.0) == OLUMSUZ    # 10bps artış
    assert ind.label_real_rate(+3.0, 5.0) == NOTR        # eşik altı


def test_dxy_falling_is_positive():
    assert ind.label_dxy(-1.0, 0.5) == OLUMLU
    assert ind.label_dxy(+1.0, 0.5) == OLUMSUZ
    assert ind.label_dxy(+0.2, 0.5) == NOTR


def test_gma_positions():
    assert ind.label_gma(price=110, gma50=105, gma200=100) == OLUMLU
    assert ind.label_gma(price=90, gma50=95, gma200=100) == OLUMSUZ
    assert ind.label_gma(price=102, gma50=98, gma200=100) == NOTR  # karışık


def test_gld_rising_is_positive():
    assert ind.label_gld(+1.0, 0.5) == OLUMLU
    assert ind.label_gld(-1.0, 0.5) == OLUMSUZ
    assert ind.label_gld(+0.1, 0.5) == NOTR


def test_real_deposit_thresholds():
    assert ind.label_real_deposit(1.0, 2.0, 8.0) == OLUMLU    # düşük reel -> altın olumlu
    assert ind.label_real_deposit(10.0, 2.0, 8.0) == OLUMSUZ  # yüksek reel -> olumsuz
    assert ind.label_real_deposit(5.0, 2.0, 8.0) == NOTR


def test_consensus_excludes_veri_yok():
    sigs = [
        Signal("a", OLUMLU, ""),
        Signal("b", OLUMSUZ, ""),
        Signal("c", YOK, ""),        # paydaya girmemeli
    ]
    c = ind.consensus(sigs)
    assert c["n"] == 2               # YOK sayılmadı
    assert c["score"] == 0


def test_consensus_direction():
    sigs = [Signal("a", OLUMLU, ""), Signal("b", OLUMLU, ""), Signal("c", NOTR, "")]
    c = ind.consensus(sigs)
    assert c["normalized"] > 0.25
    assert c["yon"] == OLUMLU


def test_consensus_all_veri_yok():
    c = ind.consensus([Signal("a", YOK, ""), Signal("b", YOK, "")])
    assert c["n"] == 0 and c["yon"] == NOTR


def test_signal_score_mapping():
    assert Signal("x", OLUMLU, "").score == 1
    assert Signal("x", OLUMSUZ, "").score == -1
    assert Signal("x", NOTR, "").score == 0
    assert Signal("x", YOK, "").score is None


# ---------------------------------------------------------------------------
# RAPOR-İÇİ ÇELİŞKİ (denetim 2026-08-28, B-12 / B-15)
# ---------------------------------------------------------------------------

def test_panel_ayni_surecte_IKI_KEZ_cekilmiyor(monkeypatch):
    """48 raporun 7'sinde panel tablosu ile kadran sinyali FARKLI payda yazdı.

    Sebep: `build_panel` bir rapor akışında iki tüketici tarafından çağrılıyor
    ve her çağrı bağımsız ağ isteği yapıyordu; bir gösterge iki çağrı arasında
    susarsa payda değişiyor, `normalized = score/n` eşiğin öbür yanına düşüp
    ETİKETİ çeviriyordu (07-16: panel "olumsuz -1/3" · kadran "notr -1/4").
    """
    indicators = ind

    indicators._PANEL_CACHE.clear()
    sayac = {"n": 0}

    def sahte(cfg):
        sayac["n"] += 1
        # ikinci çağrıda gösterge "susuyor" — eski hâlde payda değişirdi
        if sayac["n"] > 1:
            return indicators.Signal("DXY", indicators.YOK, "ağ yok")
        return indicators.Signal("DXY", indicators.OLUMSUZ, "test")

    monkeypatch.setattr(indicators, "dxy_signal", sahte)
    monkeypatch.setattr(indicators, "real_rate_signal",
                        lambda cfg: indicators.Signal("reel", indicators.YOK, "-"))
    monkeypatch.setattr(indicators, "ons_gma_signal",
                        lambda cfg: indicators.Signal("gma", indicators.YOK, "-"))
    monkeypatch.setattr(indicators, "gld_signal",
                        lambda cfg: indicators.Signal("gld", indicators.YOK, "-"))
    monkeypatch.setattr(indicators, "real_deposit_signal",
                        lambda cfg, r: indicators.Signal("mev", indicators.YOK, "-"))
    cfg = util.load_config()
    try:
        a = indicators.build_panel(cfg, None)
        b = indicators.build_panel(cfg, None)
    finally:
        indicators._PANEL_CACHE.clear()
    assert sayac["n"] == 1, (
        f"panel {sayac['n']} kez çekildi — aynı rapor iki farklı panel görebilir")
    assert a["consensus"] == b["consensus"], (
        f"iki çağrı farklı uzlaşı verdi: {a['consensus']} vs {b['consensus']}")


def test_gma_paneli_CANLI_ag_istegi_yapmiyor():
    """GMA fiyatı `ohlc_daily`'den gelmeli; canlı `GC=F` barı KİRLİ.

    Ölçüldü (12/12 rapor, 08-16…08-28): panel fiyatı özet ons'tan ortalama
    +1.2 puan yüksekti — canlı/kapanmamış vadeli kontrat barı. `label_gma` o
    kirli fiyatı TEMİZ kapanış ortalamalarıyla karşılaştırıyordu.
    """
    kaynak = util.abspath("src/indicators.py").read_text(encoding="utf-8")
    i = kaynak.find("def ons_gma_signal")
    assert i > 0
    govde = kaynak[i:kaynak.find("\ndef ", i + 10)]
    # docstring eski davranışı ANLATIYOR; denetim koda bakmalı
    govde = govde.split('"""')[-1]
    assert "yf.Ticker" not in govde, (
        "ons_gma_signal hâlâ kendi yfinance isteğini yapıyor → kapanmamış "
        "canlı bar okunur (B-15)")
    assert "load_ohlc" in govde, "GMA serisi DB'den okunmuyor"
