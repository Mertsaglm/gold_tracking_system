"""KARAR YOLU AĞA ÇIKMAZ — soket seviyesinde kanıt.

Neden bu dosya var: bu projede karar üretiminin saf olması bir tercih değil,
karnenin geçerlilik şartı. `ozellikler.py`'nin modül docstring'i kuralı yazıyor:
*"Canlı üretim ve tarihsel replay AYNI fonksiyonu çağırır."* Replay ağa çıkamaz
(2017'nin DXY'sini bugün çekmek geleceği içerir — ADR #007'de Google Trends tam
bu yüzden reddedildi). Dolayısıyla canlı yol da çıkmamalı.

Mock'lamak bu iddiayı KANITLAMAZ: mock yalnız bildiğin çağrıyı yakalar. Burada
`socket.socket` kapatılıyor — requests, urllib, yfinance, pytrends hepsi onun
üstünde. Yeni bir ağ çağrısı eklenirse hangi kütüphaneyle olursa olsun test
`AgKapaliHatasi` ile düşer.

İkinci koruma: ağ **hangi modüllerde** olduğu da kilitli. `karar.py`'ye bir
`import requests` girmesi tek satırlık bir değişikliktir ve hiçbir davranış
testi bunu görmez — `test_ag_kullanan_modul_listesi_sabit` görür.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from src import (calc, calculators, chart, dbdump, gram, karar, notify,
                 ozellikler as oz, report, signals, tahmin, util)
from tests.conftest import KOK, sentetik_db, yaz_engel_onbellegi

# Ağ ilkelini (requests/yfinance/pytrends/urllib) İÇEREBİLEN modüller.
# Liste bilinçli olarak kısa: veri çekiciler + Telegram. Karar, hesap, rapor
# ve kayıt katmanları burada YOKTUR ve olmamalı.
AG_MODULLERI = {
    "history.py",        # yfinance — tarihsel ons
    "indicators.py",     # requests (FRED) + yfinance (DXY/GLD yedeği)
    "ohlc_hist.py",      # yfinance — günlük OHLC
    "telegram_bot.py",   # requests — Telegram API
    "trends.py",         # pytrends
    "sources/evds.py",
    "sources/truncgil.py",
    "sources/yf.py",
}

AG_KALIBI = re.compile(r"^\s*(?:import requests|import yfinance|from pytrends|"
                       r"import urllib\.request|from urllib import request)",
                       re.MULTILINE)


def test_ag_kullanan_modul_listesi_sabit():
    """KİLİT TEST. Ağ yalnız veri çekicilerde ve Telegram'da olabilir.

    Karar/hesap katmanına bir ağ çağrısı girerse:
      - tarihsel replay canlıdan farklı davranır → karne sahtelenir,
      - `daily_job` adımı ağ yavaşlığında zaman aşımına düşer (FRED ölçümü:
        tek koşumda 166 saniyenin neredeyse tamamı buydu),
      - test paketi ağa bağımlı hâle gelir.
    """
    bulunan = set()
    for p in sorted(pathlib.Path(KOK / "src").glob("**/*.py")):
        if AG_KALIBI.search(p.read_text(encoding="utf-8")):
            ad = str(p.relative_to(KOK / "src"))
            bulunan.add(ad)
    fazla = bulunan - AG_MODULLERI
    assert not fazla, (f"karar/hesap katmanına ağ girdi: {sorted(fazla)} — "
                       "ağ yalnız veri çekicilerde olabilir (ADR #007-G)")


def test_conftest_ag_cekici_listesi_guncel():
    """Susturma listesi eksikse izole testler sessizce ağa çıkmaya çalışır."""
    from tests.conftest import AG_CEKICILERI
    import importlib
    for modul_adi, fn_adi in AG_CEKICILERI:
        m = importlib.import_module(modul_adi)
        assert hasattr(m, fn_adi), f"{modul_adi}.{fn_adi} artık yok — liste eskimiş"


# ------------------------------------------------------ saf çekirdek ağsız
def test_saf_hesaplar_agsiz_calisir(ag_kapali):
    """Hesap katmanı: tek bayt ağ trafiği olmadan tam sonuç üretmeli."""
    cfg = util.load_config()
    assert calc.theoretical_gram(4000.0, 47.0) > 0
    assert gram.roundtrip_cost_pct(cfg, "banka_hesap") > 0
    assert calculators.compare_instruments(cfg, 100000.0, 12)["kazanan"]
    assert gram.hukum_dogru_mu("TUT", -2.0, 1.2) is True
    assert tahmin.gram_etkisi("SAT_25", 5.0, 1.2) > 0
    assert chart.rsi([100.0 + i for i in range(40)], 14)[-1] == pytest.approx(100.0)


def test_karar_ver_agsiz(ag_kapali):
    """`karar_ver` SAF: girdisi hazır sözlükler, çıktısı hüküm."""
    cfg = util.load_config()
    engel = {"ufuklar": {cfg["karar"]["birincil_ufuk"]: {
        "gun": 21, "n_bagimsiz": 121, "taban_ortalama_pct": -1.99,
        "kazanma_pct": 36.0, "maliyet_sonrasi_kazanma_pct": 28.0,
        "en_kotu_pct": -36.2, "taktik_esik_puan": 3.19, "cekirdek_esik_puan": 1.99}}}
    k = karar.karar_ver({"reel_net_mevduat": 12.7}, cfg, engel)
    md = karar.format_karar_md(k)
    assert "HÜKÜM" in md and k["taktik"]["hukum"] == karar.TUT


def test_esik_degerlendirmesi_agsiz(ag_kapali):
    cfg = util.load_config()
    ctx = {"all_fresh": True, "prim": 9.0, "prim_z": 5.0, "spread": 1.0,
           "spread_p90": 0.1, "daily_move": 500.0, "atr": 10.0, "quarter_z": 5.0}
    alarmlar = notify.evaluate_thresholds(ctx, cfg)
    assert len(alarmlar) == 5
    gonderilecek, durum = notify.apply_cooldown(
        alarmlar, {}, "2026-07-27T10:00:00+00:00", 24, 6)
    assert len(gonderilecek) == 5 and durum["last_sent"]


def test_gap_siniflandirma_agsiz(ag_kapali):
    assert report.classify_gap(100.0, 50.0, 270.0)[0] == "ok"
    assert report.classify_gap(545.0, 217.0, 270.0)[0] == "kaynak"
    assert report.classify_gap(545.0, 500.0, 270.0)[0] == "ariza"


# ------------------------------------------------------ DB'li yollar ağsız
def test_ozellik_vektoru_agsiz(izole_kok, ag_kapali):
    """KİLİT TEST. 41 özelliğin hiçbiri ağ istemiyor; isteyen bir özellik
    eklenirse replay'de o özellik farklı davranır (ADR #007-G kesişim kuralı)."""
    cfg, _ = izole_kok
    con, tarihler = sentetik_db(cfg, gun=300)
    try:
        f = oz.feature_vector(cfg, con, tarihler[250])
        assert f["asof_date"] == tarihler[250]
        assert f["gram_teorik"] and f["reel_net_mevduat"] is not None
        assert oz.son_kapali_gun(con) == tarihler[-1]
    finally:
        con.close()


def test_tahmin_zinciri_agsiz(izole_kok, ag_kapali):
    """kaydet → giriş → çözüm → karne: tamamı yerel."""
    cfg, _ = izole_kok
    yaz_engel_onbellegi(cfg)
    con, tarihler = sentetik_db(cfg, gun=300)
    try:
        yazilan = tahmin.kaydet(cfg, con, asof_date=tarihler[200])
        assert len(yazilan) == len(cfg["karar"]["ufuklar_gun"]) * 2
        assert tahmin.girisleri_doldur(cfg, con) == len(yazilan)
        assert tahmin.cozumle(cfg, con) >= 1
        k = tahmin.karne(cfg, con)
        assert k["cozulmus"] >= 1
        assert "Tahmin Karnesi" in tahmin.format_karne_md(k)
    finally:
        con.close()


def test_canli_hukum_agsiz(izole_kok, ag_kapali):
    """`build_karar` üretimde raporun en başında çağrılıyor; ağ isterse rapor
    her akşam ağ yavaşlığına bağımlı olur."""
    cfg, _ = izole_kok
    yaz_engel_onbellegi(cfg)
    con, _ = sentetik_db(cfg, gun=300)
    con.close()
    k = karar.build_karar(cfg)
    assert k["asof_date"] and k["cekirdek"]["hukum"]
    assert "🎯 HÜKÜM" in karar.format_karar_md(k)


def test_engel_olcumu_agsiz(izole_kok, ag_kapali):
    """2561 günlük ölçüm tamamen yerel: `history_daily` + `evds_daily`."""
    cfg, _ = izole_kok
    con, _ = sentetik_db(cfg, gun=300)
    try:
        engel = gram.sat_engeli(cfg, con)
        ozet = gram.engel_ozet(cfg, engel)
        assert ozet["ufuklar"], "hiçbir ufukta ölçüm çıkmadı"
        md = gram.format_engel_md(cfg, engel, [])
        assert "Gram Engeli" in md
    finally:
        con.close()


def test_zskor_provasi_agsiz(izole_kok, ag_kapali):
    cfg, _ = izole_kok
    con, _ = sentetik_db(cfg, gun=80, prim_gun=40)
    try:
        olcum = signals.zscore_dry_run(cfg, con)
        assert olcum["gun"] == 40
        assert olcum["z_kayit_tabani"] is not None
        assert olcum["z_gun_tabani"] is not None
    finally:
        con.close()


def test_dump_restore_agsiz(izole_kok, ag_kapali):
    cfg, _ = izole_kok
    con, _ = sentetik_db(cfg, gun=50, prim_gun=10)
    con.close()
    dbdump.dump(cfg)
    assert dbdump.restore(cfg)["restored"] is True


def test_grafik_yorumu_agsiz(izole_kok, ag_kapali):
    """`build_chart(refresh=False)` DB'den okur — bot yoklama döngüsü ağda
    asılmasın diye böyle tasarlandı; varsayılan `refresh` True olursa
    `/grafik` her çağrıda yfinance bekler."""
    import inspect
    assert "refresh: bool = False" in inspect.signature(
        chart.build_chart).__str__().replace("'", "") or \
        inspect.signature(chart.build_chart).parameters["refresh"].default is False
    cfg, _ = izole_kok
    con, _ = sentetik_db(cfg, gun=300)
    con.close()
    c = chart.build_chart(cfg)
    assert not c.get("yok"), c
    assert c["spot"] and c["rsi"] is not None


def test_bildirim_baglami_agsiz(izole_kok, ag_kapali):
    """`build_context` taze CSV + DB okur; MarketCalendar tatil dosyasından."""
    cfg, tmp = izole_kok
    from tests.conftest import arsiv_csv_yaz
    con, _ = sentetik_db(cfg, gun=80, prim_gun=40)
    con.close()
    arsiv_csv_yaz(tmp)
    ctx = notify.build_context(cfg)
    assert ctx["prim"] is not None
    assert ctx["atr"] is not None


# ------------------------------------------------------ ağ düşünce çökmüyor
def test_fred_erisilemezse_none_doner_ve_onbelleklenir(monkeypatch):
    """FRED 2026-07-07'den beri üretimde ölü (ADR #006-A). Panel 6/7 gösterge
    ile çalışmaya devam etmeli; istisna fırlatmamalı."""
    from src import indicators
    monkeypatch.setattr(indicators, "_FRED_CACHE", {})
    cagri = {"n": 0}

    def _patlar(*a, **k):
        cagri["n"] += 1
        raise OSError("ağ yok")

    monkeypatch.setattr(indicators.requests, "get", _patlar)
    monkeypatch.setattr(indicators.time, "sleep", lambda *_: None)
    cfg = util.load_config()
    assert indicators._fred_csv(cfg, "DFII10") is None
    ilk = cagri["n"]
    assert indicators._fred_csv(cfg, "DFII10") is None
    assert cagri["n"] == ilk, "başarısızlık önbelleklenmiyor → her tüketici ödüyor"


def test_ag_dusunce_gostergeler_veri_yok_diyor(monkeypatch, ag_susturuldu):
    """Eksik gösterge paydadan düşer, uydurma değer üretilmez (dürüst davranış)."""
    from src import indicators
    cfg = util.load_config()
    s = indicators.real_rate_signal(cfg)
    assert s.label == indicators.YOK and s.score is None
    d = indicators.dxy_signal(cfg)
    assert d.label == indicators.YOK
