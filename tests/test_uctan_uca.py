"""UÇTAN UCA günlük koşum — Actions'ın her akşam yaptığı şeyin birebir provası.

Bu dosyanın tek bir işi var: **makine hâlâ dönüyor mu?**

Var olan 299 test parçaları ayrı ayrı doğruluyor; hiçbiri zinciri baştan sona
çalıştırmıyordu. Oysa bu projede en pahalı arızaların hepsi PARÇALAR ARASI
oldu, parçaların içinde değil:

- `history_daily`'yi hiçbir otomatik iş çağırmıyordu → 17 gün donuk (ADR #004)
- `quarter_z` hesaplanıyor ama `build_context` daima None döndürüyordu (ADR #006-C)
- `daily_job` altı adımın hatasını yutuyordu → Actions yeşil, sistem ölü (K-6)
- `asof` koruması yazılmıştı ama çağrı yolu onu geçmiyordu (L-011)

Her biri "birim testler geçiyor" hâlinde yaşandı. Bu test o boşluğu kapatır:
izole bir kökte (`tmp_path`), ağ kapalı, sentetik veriyle `daily_job.run()`
koşar ve **kullanıcının gördüğü çıktıyı** denetler.

Zaman sabitlenir (Perşembe 18:35 TR) — asof kapısı, rapor başlığı ve hafta
sonu dalları takvimden bağımsız olmalı ki test her gün aynı şeyi ölçsün.
"""
from __future__ import annotations

import json

import pytest

from src import daily_job, db, dbdump, gram, history, ohlc_hist, tahmin, util
from tests.conftest import (arsiv_csv_yaz, is_gunleri, sentetik_db,
                            yaz_engel_onbellegi)

UFUK_SAYISI = len(util.load_config()["karar"]["ufuklar_gun"])
KOL_SAYISI = 2                                   # cekirdek + taktik


@pytest.fixture
def hazir_sistem(izole_kok, sabit_zaman, ag_kapali, ag_susturuldu, monkeypatch):
    """Tam kurulu, ağı kesilmiş, sentetik bir üretim ortamı.

    Yalnız iki ağ çekicisi taklit edilir (`_yf_ons_daily`, `_yf_daily_ohlc`) ve
    ikisi de BUGÜNÜN ve HAFTA SONUNUN barını DÖNDÜRÜR — çünkü üretimde de
    öyle yapıyorlar. Testin görevi, sistemin bunları YAZMADIĞINI kanıtlamak.
    """
    cfg, kok = izole_kok
    monkeypatch.delenv("EVDS_API_KEY", raising=False)

    tarihler = is_gunleri(300)
    con, _ = sentetik_db(cfg, tarihler=tarihler, prim_gun=70)
    bugun = util.local_today()
    # Kesişimin İKİ bacağı da bugünü içersin (üretimde ölçülen durum:
    # 2026-07-24 koşumunda GC=F ve TP.DK.USD.S.YTL ikisi de aynı günü döndürdü)
    con.execute("INSERT OR REPLACE INTO evds_daily(date,series_code,value) "
                "VALUES(?,?,?)", (bugun, cfg["sources"]["evds"]["series"]["usdtry_sell"],
                                  48.0))
    con.commit()
    con.close()

    yaz_engel_onbellegi(cfg)
    arsiv_csv_yaz(kok, satir_sayisi=6)

    ons_serisi = {d: 2000.0 * (1.0004 ** i) for i, d in enumerate(tarihler)}
    ons_serisi[bugun] = 4100.0                        # bugünün YARIM barı
    monkeypatch.setattr(history, "_yf_ons_daily",
                        lambda cfg, start, min_days=200: (ons_serisi, "test"))

    def _sahte_ohlc(ticker, start):
        barlar = [{"date": d, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 0.0}
                  for d in tarihler[-8:]]
        barlar.append({"date": "2026-07-18", "o": 1.0, "h": 1.0, "l": 1.0,
                       "c": 1.0, "v": 0.0})           # CUMARTESİ hayalet barı
        barlar.append({"date": bugun, "o": 9.0, "h": 9.0, "l": 9.0,
                       "c": 9.0, "v": 0.0})           # bugünün yarım barı
        return barlar

    monkeypatch.setattr(ohlc_hist, "_yf_daily_ohlc", _sahte_ohlc)
    return cfg, kok, tarihler


# ------------------------------------------------------------------ koşum
def test_gunluk_is_bastan_sona_kosuyor(hazir_sistem):
    """KİLİT TEST. Zincirin tamamı: import → evds → ohlc → history → prova →
    tahmin → rapor. Kritik adım patlarsa `basarisiz_mi` boş DEĞİL döner."""
    cfg, kok, _ = hazir_sistem
    sonuc = daily_job.run(cfg)

    assert daily_job.basarisiz_mi(sonuc) == [], (
        f"kritik adım patladı: {sonuc.get('hatalar')}")
    # Kritik olmayan adımlar da patlamamalı — patlıyorsa sebebi görünsün
    assert not sonuc.get("hatalar"), f"adım hataları: {sonuc['hatalar']}"
    assert sonuc["rapor"], "rapor yolu dönmedi"
    assert (kok / "reports").glob("rapor_*.md"), "rapor dosyası yazılmadı"


def test_rapor_kullanicinin_bekledigi_seyi_iceriyor(hazir_sistem):
    """Rapor sözleşmesi: HÜKÜM en başta, sayılar tabloda, disclaimer sonda.

    "Kullanıcının rapordan beklediği tek şey 'bugün ne yapayım?'" (ADR #007) —
    o blok kaybolursa rapor koşmaya devam eder ve kimse fark etmez.
    """
    cfg, _, _ = hazir_sistem
    sonuc = daily_job.run(cfg)
    metin = util.abspath(sonuc["rapor"]).read_text(encoding="utf-8")

    assert "🎯 HÜKÜM" in metin
    assert "ÇEKİRDEK ALIM" in metin and "TAKTİK" in metin
    assert "SAT kapısı: KAPALI" in metin, "kapı durumu raporda görünmüyor"
    assert "Veri kesimi (asof)" in metin, "hangi güne dayandığı yazılmıyor"
    assert "Fiyat Özeti" in metin and "Prim & Makas" in metin
    assert "Veri Kalitesi" in metin
    assert metin.rstrip().endswith("yatırım tavsiyesi değildir._")
    # HÜKÜM fiyat tablosundan ÖNCE gelmeli (ilk ekranda görünsün)
    assert metin.index("🎯 HÜKÜM") < metin.index("Fiyat Özeti")


def test_hukum_bugune_degil_son_kapali_gune_dayaniyor(hazir_sistem):
    """KİLİT TEST (L-011 + ADR #008-D).

    Bugünün YARIM barı hem `_yf_ons_daily`'de hem EVDS'de var. Koruma
    KAYNAKTA olduğu için `history_daily`'ye hiç yazılmamalı; dolayısıyla
    `asof` da bugün olamaz. Bu, `predictions`'a değiştirilemez şekilde yazılan
    kaydın yarım bardan üretilmesini engelleyen tek şey.
    """
    cfg, _, tarihler = hazir_sistem
    daily_job.run(cfg)
    bugun = util.local_today()
    con = db.connect(cfg)
    try:
        son = con.execute("SELECT MAX(date) FROM history_daily").fetchone()[0]
        assert son != bugun, "bugünün yarım barı history_daily'ye yazıldı"
        asoflar = {r[0] for r in con.execute("SELECT DISTINCT asof_date FROM predictions")}
        assert asoflar and bugun not in asoflar
        assert asoflar == {son}, f"asof tek kaynaktan gelmiyor: {asoflar}"
    finally:
        con.close()


def test_hafta_sonu_ve_bugun_barlari_ohlc_tablosuna_girmiyor(hazir_sistem):
    """ADR #008-G: hayalet hafta sonu barı `kur_atr`'ı %7.17 şişiriyordu.
    İki filtre birlikte çalışmazsa (bugün + hafta sonu) hayalet KALICI olur —
    `_upsert` hiçbir zaman silmiyor."""
    cfg, _, _ = hazir_sistem
    daily_job.run(cfg)
    con = db.connect(cfg)
    try:
        satirlar = [r[0] for r in con.execute("SELECT date FROM ohlc_daily")]
        assert "2026-07-18" not in satirlar, "Cumartesi hayalet barı yazıldı"
        assert util.local_today() not in satirlar, "bugünün yarım barı yazıldı"
        from datetime import date
        hafta_sonu = [d for d in satirlar if date.fromisoformat(d).weekday() >= 5]
        assert not hafta_sonu, f"tabloda hafta sonu barı var: {hafta_sonu}"
    finally:
        con.close()


def test_her_asof_icin_ufuk_x_kol_kadar_hukum_yazilir(hazir_sistem):
    """Kaçınma yasak: her asof TAM OLARAK ufuk × kol kadar satır üretir.
    Eksik satır, karneyi seçerek temizlemenin kapısıdır."""
    cfg, _, _ = hazir_sistem
    sonuc = daily_job.run(cfg)
    assert sonuc["tahmin_kaydedilen"] == UFUK_SAYISI * KOL_SAYISI
    con = db.connect(cfg)
    try:
        kombinasyon = con.execute(
            "SELECT COUNT(DISTINCT horizon_days || kol) FROM predictions").fetchone()[0]
        assert kombinasyon == UFUK_SAYISI * KOL_SAYISI
        # Kapı kapalı → kayıtlı her hüküm ya AL_* (çekirdek) ya TUT (taktik)
        hukumler = {r[0] for r in con.execute("SELECT DISTINCT hukum FROM predictions")}
        assert not any(h.startswith("SAT") for h in hukumler), (
            f"kapı kapalıyken SAT kaydedildi: {hukumler}")
        assert {r[0] for r in con.execute("SELECT DISTINCT kapi_acik FROM predictions")} \
            == {0}
    finally:
        con.close()


def test_ayni_gun_ikinci_kosum_cift_kayit_yapmaz(hazir_sistem):
    """`workflow_dispatch` ile aynı gün elle koşum yapılabiliyor; UNIQUE kısıtı
    olmasa karne çift sayardı."""
    cfg, _, _ = hazir_sistem
    daily_job.run(cfg)
    ikinci = daily_job.run(cfg)
    assert ikinci["tahmin_kaydedilen"] == 0
    con = db.connect(cfg)
    try:
        assert con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == \
            UFUK_SAYISI * KOL_SAYISI
    finally:
        con.close()


def test_zskor_provasi_gunde_bir_satir_ekliyor(hazir_sistem):
    """ADR #006-B: kapı açılmadan dağılımı öğrenmenin tek yolu. Dosya
    append-only; koşum başına bir satır."""
    cfg, kok, _ = hazir_sistem
    daily_job.run(cfg)
    yol = util.abspath(cfg["stats"]["zskor_prova_dosyasi"])
    satirlar = [json.loads(s) for s in yol.read_text(encoding="utf-8").splitlines() if s]
    assert len(satirlar) == 1
    kayit = satirlar[0]
    for alan in ("gun", "z_kayit_tabani", "z_gun_tabani", "tetiklenir_kayit",
                 "tetiklenir_gun", "ts_utc"):
        assert alan in kayit, f"prova kaydında {alan} yok"
    assert kayit["gun"] == 70


def test_kapi_kapaliyken_karne_olcum_icermedigini_soyluyor(hazir_sistem):
    """KİLİT TEST (ADR #008-A/B). Karne "fark +0.0p" yazamaz; yazarsa totoloji
    ölçüm gibi okunur ve Ekim'deki kapı kararı ona dayanır."""
    cfg, _, _ = hazir_sistem
    sonuc = daily_job.run(cfg)
    metin = util.abspath(sonuc["rapor"]).read_text(encoding="utf-8")
    assert "fark +0.0p" not in metin
    con = db.connect(cfg)
    try:
        k = tahmin.karne(cfg, con)
        assert k["olculebilir_mi"] is False
        assert k["sat_hukum_sayisi"] == 0
    finally:
        con.close()


def test_telegram_kapaliyken_dis_dunyaya_cikis_yok(hazir_sistem):
    """`telegram.enabled: false` iken hiçbir mesaj/outbox kaydı üretilmemeli
    (ağ da kapalı olduğu için gerçekten denerse test patlar)."""
    cfg, kok, _ = hazir_sistem
    sonuc = daily_job.run(cfg)
    assert "telegram" not in sonuc
    assert not (kok / "data" / "telegram_outbox.jsonl").exists()


# ------------------------------------------------------------ Actions döngüsü
def test_actions_dongusu_veriyi_koruyor(hazir_sistem):
    """KİLİT TEST — Actions'ın gerçek döngüsü: iş → dump → (DB yok) → restore.

    Actions stateless: her koşum DB'yi dump'tan kuruyor. Bu testin düşmesi
    "üretimde her gün veri kaybediyoruz" demektir (L-009 ailesi).
    """
    cfg, _, _ = hazir_sistem
    daily_job.run(cfg)

    con = db.connect(cfg)
    once = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t, _, _ in dbdump._TABLES}
    con.close()

    dbdump.dump(cfg)
    dbdump.restore(cfg)

    con = db.connect(cfg)
    try:
        sonra = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t, _, _ in dbdump._TABLES}
    finally:
        con.close()
    assert sonra == once, f"restore'da satır kaybı: {once} → {sonra}"
    assert once["predictions"] == UFUK_SAYISI * KOL_SAYISI


def test_restore_sonrasi_ikinci_gun_kosumu_calisiyor(hazir_sistem):
    """İki günlük ardışık koşum: gün 1 → dump → restore → gün 2.

    Üretimde her gün böyle oluyor; ikinci günün asof'u ilerlemeli ve yeni
    tahminler önceki günün üstüne YAZILMAMALI.
    """
    cfg, _, tarihler = hazir_sistem
    daily_job.run(cfg)
    dbdump.dump(cfg)
    dbdump.restore(cfg)

    con = db.connect(cfg)
    try:
        # gün 2: bir sonraki iş günü kapanmış say
        yeni = tahmin.kaydet(cfg, con, asof_date=tarihler[-2])
        assert len(yeni) == UFUK_SAYISI * KOL_SAYISI
        asoflar = {r[0] for r in con.execute("SELECT DISTINCT asof_date FROM predictions")}
        assert len(asoflar) == 2, "ikinci günün kaydı birincinin üstüne yazıldı"
    finally:
        con.close()


def test_kaydet_giris_cozum_zinciri_tam_donuyor(hazir_sistem):
    """STATE.md'nin ~2026-08-03 DoD'si: zincirin canlıda ilk TAM dönüşü.

    Burada takvim beklemeden ölçülüyor: geçmiş bir asof için hüküm yaz, girişi
    doldur, vadesi dolanı çöz → `prediction_outcomes` satırı oluşmalı ve
    `/karne` "1 çözülmüş" demeli.
    """
    cfg, _, tarihler = hazir_sistem
    con = db.connect(cfg)
    try:
        eski_asof = tarihler[200]
        yazilan = tahmin.kaydet(cfg, con, asof_date=eski_asof)
        assert yazilan
        assert tahmin.girisleri_doldur(cfg, con) == len(yazilan)
        cozulen = tahmin.cozumle(cfg, con)
        assert cozulen == len(yazilan), "vadesi dolan tahminler çözülmedi"

        satir = con.execute(
            "SELECT e.giris_date, o.cikis_date, o.gram_carry_kazanc_pct, "
            "o.roundtrip_maliyet_pct, o.taban_dogru FROM predictions p "
            "JOIN prediction_entries e ON e.prediction_id=p.id "
            "JOIN prediction_outcomes o ON o.prediction_id=p.id "
            "WHERE p.horizon_days=? AND p.kol='taktik'",
            (cfg["karar"]["ufuklar_gun"][cfg["karar"]["birincil_ufuk"]],)).fetchone()
        assert satir["giris_date"] > eski_asof, "giriş asof'tan sonra olmalı (T)"
        assert satir["cikis_date"] > satir["giris_date"]
        assert satir["roundtrip_maliyet_pct"] == pytest.approx(
            gram.roundtrip_cost_pct(cfg, cfg["karar"]["enstruman"]))
        karne = tahmin.karne(cfg, con)
        assert karne["cozulmus"] == UFUK_SAYISI      # taktik kolun üç ufku
        md = tahmin.format_karne_md(karne)
        assert f"| Çözülmüş tahmin | {UFUK_SAYISI} |" in md
        assert "ÖLÇÜM İÇERMİYOR" in md, "hiç SAT yok → karne ölçüm içermiyor demeli"
    finally:
        con.close()


def test_giris_fiyati_hukum_aninda_bilinmeyen_gunden(hazir_sistem):
    """ADR #007-F: hüküm asof=T−1'de verilir, giriş T'nin kapanışıdır ve o an
    HENÜZ BİLİNMEZ. Aynı satıra yazmak look-ahead olurdu."""
    cfg, _, tarihler = hazir_sistem
    con = db.connect(cfg)
    try:
        tahmin.kaydet(cfg, con, asof_date=tarihler[100])
        # giriş henüz yok
        assert con.execute("SELECT COUNT(*) FROM prediction_entries").fetchone()[0] == 0
        tahmin.girisleri_doldur(cfg, con)
        giris = con.execute("SELECT giris_date FROM prediction_entries").fetchone()[0]
        assert giris == tarihler[101], "giriş T günü değil"
    finally:
        con.close()


def test_kritik_adim_patlarsa_is_basarisiz(hazir_sistem, monkeypatch):
    """K-6'nın davranış tarafı: rapor patlarsa `basarisiz_mi` boş dönmemeli,
    yoksa Actions yeşil kalır ve dump+commit yarım veriyle çalışır."""
    cfg, _, _ = hazir_sistem
    from src import report

    def _patla(*a, **k):
        raise RuntimeError("test: rapor çöktü")

    monkeypatch.setattr(report, "build_report", _patla)
    monkeypatch.setattr(report, "build_weekly_report", _patla)
    sonuc = daily_job.run(cfg)
    assert daily_job.basarisiz_mi(sonuc) == ["rapor"]
    assert "rapor" in sonuc["hatalar"]


def test_kritik_olmayan_adim_patlarsa_rapor_yine_cikiyor(hazir_sistem, monkeypatch):
    """OHLC/history/EVDS bir gün patlarsa rapor YİNE anlamlıdır ve ertesi gün
    kendini onarır — bu yüzden onlar kritik listede değil."""
    cfg, _, _ = hazir_sistem

    def _patla(*a, **k):
        raise RuntimeError("test: yfinance çöktü")

    monkeypatch.setattr(ohlc_hist, "update_ohlc_daily", _patla)
    monkeypatch.setattr(history, "update_recent", _patla)
    sonuc = daily_job.run(cfg)
    assert daily_job.basarisiz_mi(sonuc) == []
    assert set(sonuc["hatalar"]) == {"ohlc", "history"}
    assert sonuc["rapor"]
