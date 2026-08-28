"""KİLİT: prim'in iki bacağı bağımsız mı? (denetim 2026-08-28, B-03/B-21)

Bu dosyanın var oluş sebebi bir ARIZA SINIFI: ADR #013 ons'u gram ile aynı
satıcıya taşıyınca `gram_has ≡ ons × kur × 0.995` oldu, yani ons prim
formülünde SADELEŞTİ ve "Kapalıçarşı primi" satıcının kendi saflık çarpanını
ölçmeye başladı. 8 gün boyunca 855 test yeşil kaldı, `test_dejenere_metrik.py`
yakalamadı, kapı sayacı ilerlemeye devam etti — çünkü hiçbir kontrol
"iki serim gerçekten bağımsız mı?" diye sormuyordu.

Sentetik veri bu tuzağı ÜRETEMEZ (test fixture'ında ons ve gram bağımsız
kurulur, kimlik hiç oluşmaz → test vacuous geçer). Bu yüzden testler
kimliği BİLEREK kurgular ve tetiklendiğini ayrıca assert eder.
"""
from __future__ import annotations

import csv

import pytest
import yaml

from src import calc, import_actions
from src.market_calendar import MarketCalendar

TROY = 31.1034768
SAFLIK = 0.995


@pytest.fixture
def cfg():
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------
# 1) Saf fonksiyon: kimliği ayırt ediyor mu?
# --------------------------------------------------------------------------

def _kimlik_oranlari(n: int):
    """Gram fiyatı ons'tan TÜRETİLMİŞ: oran sabit, yalnız yuvarlama oynuyor."""
    out = []
    for i in range(n):
        ons = 4600.0 + i * 3.7                     # ons gün içinde geziniyor
        usd = 48.0 + i * 0.004                     # kur da geziniyor
        teorik = ons / TROY * usd
        gram = round(teorik * SAFLIK, 2)           # satıcı 2 ondalığa yuvarlıyor
        out.append(gram / teorik)
    return out


def _gercek_oranlari(n: int):
    """Gram BAĞIMSIZ bir piyasada oluşuyor: prim gün içinde geziniyor."""
    out = []
    for i in range(n):
        ons = 4600.0 + i * 3.7
        usd = 48.0 + i * 0.004
        teorik = ons / TROY * usd
        prim = -0.6 + 0.15 * ((i % 7) - 3) / 3.0   # ±0.15 puan gün-içi salınım
        gram = round(teorik * SAFLIK * (1 + prim / 100.0), 2)
        out.append(gram / teorik)
    return out


def test_kimlik_yakalanir(cfg):
    esik = cfg["stats"]["bagimsizlik_cv_esigi"]
    minr = cfg["stats"]["bagimsizlik_min_kayit"]
    oranlar = _kimlik_oranlari(30)
    cv = calc.bagimsizlik_cv(oranlar)
    assert cv is not None and cv < esik, f"kurgu kimliği üretmedi (cv={cv:.2e})"
    assert calc.turetilmis_mi(oranlar, esik, minr) is True


def test_gercek_olcum_yakalanmaz(cfg):
    esik = cfg["stats"]["bagimsizlik_cv_esigi"]
    minr = cfg["stats"]["bagimsizlik_min_kayit"]
    oranlar = _gercek_oranlari(30)
    cv = calc.bagimsizlik_cv(oranlar)
    # tetikleyicinin gerçekten kurulduğunu doğrula — yoksa test vacuous geçer
    assert cv is not None and cv > esik, f"kurgu gerçek ölçüm üretmedi (cv={cv:.2e})"
    assert calc.turetilmis_mi(oranlar, esik, minr) is False


def test_az_kayitta_hukum_verilmez(cfg):
    esik = cfg["stats"]["bagimsizlik_cv_esigi"]
    minr = cfg["stats"]["bagimsizlik_min_kayit"]
    assert calc.turetilmis_mi(_kimlik_oranlari(minr - 1), esik, minr) is None


def test_cv_saflik_carpanindan_bagimsiz():
    """Değişim katsayısı ölçek-bağımsız olmalı: 995/1000 çarpanı eşiği kaydırmasın."""
    a = [1.0000, 1.0002, 0.9999, 1.0001]
    b = [x * SAFLIK for x in a]
    assert calc.bagimsizlik_cv(a) == pytest.approx(calc.bagimsizlik_cv(b), rel=1e-12)


# --------------------------------------------------------------------------
# 2) Üretim verisi: nöbetçi GERÇEK arşivde iki yönlü doğru çalışıyor mu?
#    (sentetik testin yakalayamadığı yer tam olarak burasıydı)
# --------------------------------------------------------------------------

def test_uretim_arsivinde_iki_yonlu(cfg, tmp_path):
    """Nöbetçi 08-17 sonrasında ateşlemeli, 07-07…07-28 arasında ATEŞLEMEMELİ."""
    import glob
    files = sorted(glob.glob("data/archive/*.csv"))
    if not files:
        pytest.skip("arşiv yok")
    cal = MarketCalendar(cfg)
    gunler = import_actions.turetilmis_gunler(cfg, files, cal)
    if not gunler:
        pytest.skip("nöbetçi kapalı")

    eski = {g: v for g, v in gunler.items() if "2026-07-07" <= g <= "2026-07-28"}
    yeni = {g: v for g, v in gunler.items() if g >= "2026-08-17"}
    # tetikleyicinin var olduğunu doğrula
    assert eski, "yfinance-ons dönemi arşivde yok — test vacuous"
    assert yeni, "Truncgil-ons dönemi arşivde yok — test vacuous"

    assert not any(eski.values()), (
        f"gerçek ölçüm dönemi türetilmiş sanıldı: "
        f"{[g for g, v in eski.items() if v]}")
    assert all(yeni.values()), (
        f"kimlik dönemi temiz sanıldı: {[g for g, v in yeni.items() if not v]}")


def test_turetilmis_gunler_hafta_sonunu_saymaz(cfg, tmp_path):
    """Hafta sonu tüm alanlar donar → oran sabit görünür; bu kimlik DEĞİLDİR."""
    p = tmp_path / "2026-08.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ts_utc", "ons_usd", "usdtry", "gram_altin_buy",
                    "gram_altin_sell", "gram_has_buy", "gram_has_sell",
                    "ceyrek_buy", "ceyrek_sell", "usd_buy", "usd_sell"])
        # 2026-08-22 Cumartesi — donmuş, tekrar eden satırlar
        for i in range(20):
            w.writerow([f"2026-08-22T{i % 24:02d}:00:00+00:00", 4600.0, 48.0,
                        7000, 7000, 6965, 6965, 11000, 11200, 47.99, 48.01])
    cal = MarketCalendar(cfg)
    gunler = import_actions.turetilmis_gunler(cfg, [str(p)], cal)
    assert "2026-08-22" not in gunler, (
        "hafta sonu donmuş kayıtlar 'türetilmiş' sayıldı — nöbetçi forex "
        "takvimini atlıyor")
