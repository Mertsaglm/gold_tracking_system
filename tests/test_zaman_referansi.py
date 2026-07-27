"""ZAMAN REFERANSI — "hangi gün?" sorusunun tek bir doğru cevabı var.

Bu projede zaman bir detay değil, `asof` garantisinin taşıyıcısı. `util.local_today`
docstring'i sebebi yazıyor: *"UTC değil YEREL gün: GC=F ~21:00 UTC (00:00 TR)
kapanıyor, yani D günü barı ancak D+1'in TR gününde tam kapanmış sayılır. UTC
kullanmak, TR'de gece 01:00'de koşan bir işte o günün yarım barını 'kapanmış'
gösterirdi."*

Bir modeli en kolay kandıran "sadeleştirme" tam budur: `local_today()` yerine
`datetime.utcnow().date()`. Kod çalışmaya devam eder, testlerin çoğu geçer, ama
yılın belli saatlerinde yarım bar kapanmış sayılır ve `predictions`'a
DEĞİŞTİRİLEMEZ şekilde yazılır. Buradaki testler o farkı sabit saatlerle ölçer.

Ayrıca üretim saatinin (cron 15:35 UTC = 18:35 TR) iki referansı ÇAKIŞTIRDIĞI
kilitlenir: yazma yolu TR gününü, grafik okuma yolu UTC gününü kullanıyor;
üretim saatinde ikisi aynı gün olduğu için bu fark zararsız. Cron gece yarısına
taşınırsa test düşer ve farkın zararsız olmaktan çıktığını söyler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import yaml

from src import util
from src.market_calendar import MarketCalendar
from tests.conftest import KOK

CFG = util.load_config()


def _an(y, ay, g, saat, dk=0) -> datetime:
    return datetime(y, ay, g, saat, dk, tzinfo=timezone.utc)


@pytest.fixture
def sabitle(monkeypatch):
    def _uygula(dt: datetime):
        monkeypatch.setattr(util, "utcnow", lambda: dt)
    return _uygula


# ------------------------------------------------------------ yerel gün
def test_yerel_gun_gece_yarisindan_sonra_ilerliyor(sabitle):
    """22:30 UTC = 01:30 TR (ertesi gün). Yerel gün ilerlemiş olmalı."""
    sabitle(_an(2026, 7, 23, 22, 30))
    assert util.local_today() == "2026-07-24"
    assert util.utcnow().date().isoformat() == "2026-07-23"   # UTC hâlâ dün


def test_yerel_gun_sabah_utc_ile_ayni(sabitle):
    sabitle(_an(2026, 7, 23, 6, 0))
    assert util.local_today() == "2026-07-23"


def test_yerel_gun_uretim_saatinde_utc_ile_AYNI(sabitle):
    """KİLİT TEST. Cron 15:35 UTC = 18:35 TR → iki referans aynı günü verir.

    Bu çakışma bir tesadüf değil, bir GÜVENLİK PAYI: yazma yolu (`history`,
    `ohlc_hist`) TR gününü, grafik okuma yolu (`chart`, `grafik_ciz`) UTC
    gününü kullanıyor. Üretim saatinde ikisi eşit olduğu için fark zararsız.
    Cron 21:00 UTC sonrasına taşınırsa eşitlik bozulur ve aynı barı bir yol
    "kapandı" diğeri "kapanmadı" sayar.
    """
    cron = yaml.safe_load((KOK / ".github/workflows/daily.yml").read_text(
        encoding="utf-8"))
    tetik = cron.get("on", cron.get(True))
    dk, saat = tetik["schedule"][0]["cron"].split()[:2]
    sabitle(_an(2026, 7, 23, int(saat), int(dk)))
    assert util.local_today() == util.utcnow().date().isoformat(), (
        "cron saatinde TR ve UTC günleri ayrıştı — yazma/okuma filtreleri "
        "farklı gün görür")


def test_yerel_gun_ofseti_configten_ve_dst_yok():
    """TR sabit UTC+3, yaz saati uygulaması YOK. Ofsetin config'te olması
    değiştirilebilirliği değil, TEK KAYNAK olmasını sağlıyor."""
    assert CFG["timezone_offset_hours"] == 3
    kis = util.to_local(_an(2026, 1, 15, 12, 0))
    yaz = util.to_local(_an(2026, 7, 15, 12, 0))
    assert kis.utcoffset() == yaz.utcoffset() == timedelta(hours=3)


def test_iso_daima_utcye_normalize_ediyor():
    """DB'ye yazılan zaman damgaları karşılaştırılabilir olmalı: karışık ofsetli
    ISO metinleri sıralaması bozar (`prim_history.ts_utc` sıralamayla okunuyor)."""
    yerel = datetime(2026, 7, 23, 18, 35, tzinfo=util.tz_local(3))
    assert util.iso(yerel).endswith("+00:00")
    assert util.iso(yerel).startswith("2026-07-23T15:35")
    # naive girdi UTC varsayılır
    assert util.iso(datetime(2026, 7, 23, 15, 35)).startswith("2026-07-23T15:35")


def test_ts_utc_metinleri_kronolojik_siralanabiliyor():
    """`ORDER BY ts_utc` doğru çalışsın diye: ISO-8601 + sabit ofset = metin
    sıralaması = zaman sıralaması."""
    anlar = [util.iso(_an(2026, 7, 23, s)) for s in (0, 5, 9, 15, 23)]
    assert anlar == sorted(anlar)


# ------------------------------------------------------------ forex seansı
@pytest.mark.parametrize("an,acik", [
    (_an(2026, 7, 22, 12), True),      # Çarşamba öğlen
    (_an(2026, 7, 24, 20, 59), True),  # Cuma 20:59 UTC — kapanıştan hemen önce
    (_an(2026, 7, 24, 21, 0), False),  # Cuma 21:00 UTC — kapanış
    (_an(2026, 7, 25, 12), False),     # Cumartesi — tam kapalı
    (_an(2026, 7, 26, 21, 59), False),  # Pazar 21:59 — açılıştan önce
    (_an(2026, 7, 26, 22, 0), True),   # Pazar 22:00 — açılış
])
def test_forex_seans_sinirlari(an, acik):
    """Seans sınırları config'ten (`forex_open_sunday_utc_hour` /
    `forex_close_friday_utc_hour`). Sınır kayarsa hafta sonu kayıtları geçerli
    sayılır ve z-skor tabanına girer."""
    cal = MarketCalendar(CFG)
    assert cal.is_forex_open(an) is acik
    assert cal.is_weekend_closed_forex(an) is (not acik)


def test_tatil_dosyasi_yuklenip_okunuyor():
    """`holidays_tr.yaml` yanlış yerde olsa MarketCalendar patlar; sessiz
    bozulma olmasın diye içerik de doğrulanıyor."""
    cal = MarketCalendar(CFG)
    assert cal.is_tr_holiday(_an(2026, 4, 23, 12)) is True     # Ulusal Egemenlik
    assert cal.is_tr_holiday(_an(2026, 4, 24, 12)) is False
    assert cal.is_us_gold_holiday(_an(2026, 12, 25, 12)) is True
    assert cal.is_us_gold_holiday(_an(2026, 12, 24, 12)) is False


def test_tatil_referanslari_bilincli_olarak_farkli():
    """TR tatili YEREL güne, ABD tatili UTC güne bakar — kasıtlı asimetri:
    biri fiziki Kapalıçarşı takvimi, diğeri CME seans takvimi. Aynı referansa
    çekmek ikisinden birini kaydırır."""
    import inspect
    assert "_local_date_str" in inspect.getsource(MarketCalendar.is_tr_holiday)
    assert "now_utc.date()" in inspect.getsource(MarketCalendar.is_us_gold_holiday)


@pytest.mark.parametrize("saat,gece", [(0, False), (1, True), (7, True),
                                       (8, False), (12, False), (23, False)])
def test_gece_penceresi_yerel_saatle(saat, gece):
    """Gece penceresi (01:00-08:00 TR) truncgil bayatlama eşiğini gevşetiyor:
    düşük likidite saatlerinde 1 saatlik veri normal. UTC'ye kayarsa eşik
    yanlış saatlerde gevşer."""
    cal = MarketCalendar(CFG)
    yerel = datetime(2026, 7, 23, saat, tzinfo=util.tz_local(3))
    assert cal.is_night_local(yerel.astimezone(timezone.utc)) is gece


def test_hafta_sonu_yerel_takvimle():
    cal = MarketCalendar(CFG)
    assert cal.is_weekend_local(_an(2026, 7, 25, 12)) is True     # Cumartesi
    assert cal.is_weekend_local(_an(2026, 7, 24, 23)) is True      # Cuma 23 UTC = Cmt 02 TR
    assert cal.is_weekend_local(_an(2026, 7, 24, 12)) is False


# ------------------------------------------------------------ pencere hesapları
def test_history_guncellemesi_gerideki_pencereyi_kullaniyor(sabitle):
    """`update_recent(days=45)`: ATR(14) penceresine tampon bırakır. Pencere
    kısalırsa ATR yeniden hesaplanamaz ve alarm eşiği donar (ADR #004)."""
    from src import history
    sabitle(_an(2026, 7, 23, 15, 35))
    cagri = {}

    def _yakala(cfg, start, min_days=200):
        cagri["start"], cagri["min_days"] = start, min_days
        return {}, None

    import unittest.mock as mock
    with mock.patch.object(history, "_yf_ons_daily", _yakala):
        history.update_recent(util.load_config(), days=45)
    assert cagri["start"] == "2026-06-08"                  # 45 gün geride
    assert cagri["min_days"] == 20, "kısa pencerede 200 gün eşiği asla dolmaz"


def test_ohlc_lookback_penceresi_bugunu_kapsiyor(sabitle):
    """Bugünün barı yazılmıyor ama YARIN yazılabilmesi için lookback penceresi
    onu yeniden çekmeye yetmeli (kayıp yok gerekçesi buna dayanıyor)."""
    assert CFG["chart"]["ohlc"]["guncelleme_lookback_gun"] >= 2


def test_zaman_damgasi_cekim_aninda_aliniyor():
    """`archive_fetch` timestamp'i çekimden ÖNCE alıyor: sonra alınsa ağ
    gecikmesi (retry ile saniyeler) veriye zaman kayması olarak yazılırdı."""
    kaynak = (KOK / "src" / "archive_fetch.py").read_text(encoding="utf-8")
    ts_satiri = kaynak.index("ts = datetime.now")
    truncgil_satiri = kaynak.index("truncgil.fetch")
    assert ts_satiri < truncgil_satiri
