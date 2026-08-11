"""RAPOR ÇIKTISI SÖZLEŞMESİ — kullanıcının gerçekten gördüğü şey.

Rapor bu projenin tek arayüzü. Bir hesap doğru olabilir ama rapora düşmüyorsa
kullanıcı için YOKTUR — ADR #006-C'de tam bu oldu: `quarter_z` alarm yoluna
bağlandı, rapora bağlanmadı; kapı açıldığında kullanıcı "çeyrek |z| > 2" uyarısı
alacak ama tetikleyen sayıyı hiçbir yerde göremeyecekti. Aynı sınıf hata L-008
olarak da kayıtlı: "bir değer üretmek onu bağlamak değildir."

Bu yüzden testler çıktının İÇERİĞİNİ denetler:
  - hangi bölümler var (HÜKÜM · fiyat · prim/makas · veri kalitesi · disclaimer)
  - eşiği tetikleyen sayılar GÖRÜNÜYOR mu
  - iki farklı olgu (prim boşluğu / çekim boşluğu) ayrı kelimelerle mi yazılıyor
    (ADR #005: bu belirsizlik gerçek bir yanlış alarma yol açtı)
  - Telegram'a giden metin sayıları kaybetmiyor mu

Kırılganlık dengesi: tam metin (golden file) karşılaştırması YAPILMIYOR — rapor
her gün değişiyor ve golden dosya her değişiklikte gürültülü biçimde düşerdi.
Bunun yerine ANLAM taşıyan sabitler aranıyor.
"""
from __future__ import annotations

import pytest

from src import db, karar, report, telegram_bot, util
from tests.conftest import arsiv_csv_yaz, sentetik_db, yaz_engel_onbellegi


@pytest.fixture
def rapor_ortami(izole_kok, sabit_zaman, ag_kapali, ag_susturuldu):
    cfg, kok = izole_kok
    yaz_engel_onbellegi(cfg)
    arsiv_csv_yaz(kok, satir_sayisi=8)
    return cfg, kok


def _rapor(cfg, prim_gun: int, gun: int = 300) -> str:
    con, _ = sentetik_db(cfg, gun=gun, prim_gun=prim_gun)
    con.close()
    return report.build_report(cfg)


# ------------------------------------------------------------ boş kurulum
def test_bos_dbde_rapor_cokmez(rapor_ortami):
    """İlk kurulumda (toplayıcı yeni başlamış) rapor anlamlı bir cümle yazmalı,
    istisna fırlatmamalı — `daily.yml` rapor adımı KRİTİK, patlarsa exit 1."""
    cfg, _ = rapor_ortami
    metin = report.build_report(cfg)
    assert "Henüz prim verisi yok" in metin
    assert metin.startswith("# 🥇 Altın Günlük Rapor")


# ------------------------------------------------------------ z-skor kapısı
def test_kapi_kapaliyken_rapor_ilerlemeyi_gun_cinsinden_yaziyor(rapor_ortami):
    """Kapı GÜN sayar (Faz 7). Rapor "N/60 gün" yazmazsa kullanıcı ilerlemeyi
    takip edemez — STATE.md takvimi "tahmin etme, rapordan oku" diyor."""
    cfg, _ = rapor_ortami
    metin = _rapor(cfg, prim_gun=40)
    assert "arşiv birikiyor" in metin
    assert "40/60 gün" in metin


def test_kapi_acilinca_prim_VE_ceyrek_z_gorunuyor(rapor_ortami):
    """KİLİT TEST (ADR #006-C yarım bağlama).

    Kapı açıkken hem prim z hem ÇEYREK z raporda olmalı: ikisi de alarm
    üretebiliyor ve tetikleyen sayının görünmemesi tutarsızlık olur.
    Ayrıca sezon düzeltmesi olmadığı da yazılmalı — sınır gizlenmiyor.
    """
    cfg, _ = rapor_ortami
    metin = _rapor(cfg, prim_gun=70)
    assert "Prim z-skoru" in metin
    assert "Çeyrek primi z-skoru" in metin, "çeyrek z rapora bağlı değil (ADR #006-C)"
    assert "sezon düzeltmesi yok" in metin


# ------------------------------------------------------------ ADR #005: dil
def test_prim_bosluguyla_cekim_boslugu_ayri_kelimelerle(rapor_ortami):
    """ADR #005: iki FARKLI olgu neredeyse eşanlamlı kelimelerle yazılıyordu ve
    kaynak kalitesi sorunu "altyapı arızası" sanılıyordu (545 dk yanlış alarmı)."""
    cfg, _ = rapor_ortami
    metin = _rapor(cfg, prim_gun=40)
    assert "en uzun **prim** boşluğu" in metin
    assert "en uzun **çekim** boşluğu" in metin


def test_kaynak_kalitesi_actions_arizasi_gibi_raporlanmiyor():
    """`classify_gap` saf fonksiyonu: Actions düzgün çalıştıysa mesaj ⚠️ değil
    ℹ️ olmalı ve "Actions kontrol edilmeli" DEMEMELİ."""
    seviye, mesaj = report.classify_gap(545.0, 217.0, 270.0)
    assert seviye == "kaynak"
    assert "Actions kontrol edilmeli" not in mesaj
    assert "kaynağın boş dönmesinden" in mesaj
    seviye2, mesaj2 = report.classify_gap(545.0, 500.0, 270.0)
    assert seviye2 == "ariza" and "Actions kontrol edilmeli" in mesaj2


def test_kapsama_gozlemlenen_ritme_gore_hesapliyor(rapor_ortami):
    """ADR #003/#005: beklenen kayıt NOMİNAL cron'a göre hesaplanırsa sağlıklı
    sistem "%16 kapsama" gösterir ve her gün yanlış alarm üretir."""
    cfg, _ = rapor_ortami
    assert report.effective_freq_minutes(cfg) == \
        cfg["alerts"]["archive_observed_freq_minutes"]
    con, _ = sentetik_db(cfg, gun=10, prim_gun=5)
    try:
        kapsama = report.coverage_report(con, cfg, 24)
        assert kapsama["expected"] == int(24 * 60 / 90)
    finally:
        con.close()
    # collector moduna geçilirse ritim poll_seconds'tan gelir (ayrı senaryo)
    c2 = dict(cfg, runtime_mode="collector")
    assert report.effective_freq_minutes(c2) == \
        cfg["sources"]["truncgil"]["poll_seconds"] / 60.0


# ------------------------------------------------------------ hüküm bloğu
def test_hukum_blogu_raporun_en_basinda(rapor_ortami):
    """"Sinyaller eskiden 8. bölümdeydi ve kimse oraya kadar okumuyordu"
    (report.py yorumu). Blok fiyat tablosundan önce gelmeli."""
    cfg, _ = rapor_ortami
    metin = _rapor(cfg, prim_gun=40)
    assert metin.index("🎯 HÜKÜM") < metin.index("## Fiyat Özeti")


def test_karar_bloku_olcumu_gerekceyle_veriyor(rapor_ortami):
    """Hüküm gerekçesi ölçüme dayanmalı: taban, N ve eşik görünmeli.
    "Çünkü öyle" diyen bir gerekçe yanlışlanamaz."""
    cfg, _ = rapor_ortami
    con, _ = sentetik_db(cfg, gun=300)
    con.close()
    md = karar.format_karar_md(karar.build_karar(cfg))
    assert "Ölçülen taban" in md
    assert "bağımsız pencere" in md
    assert "SAT kapısı: KAPALI" in md
    assert "yatırım tavsiyesi değildir" in md or "TAKTİK" in md


def test_karne_yokken_iddia_yok_diyor(rapor_ortami):
    """Sicil yoksa bunu SÖYLEMEK zorunda: sessiz kalmak "sicilim iyi" izlenimi
    verirdi (karar.py yorumu)."""
    from src import tahmin
    cfg, _ = rapor_ortami
    con, _ = sentetik_db(cfg, gun=300)
    try:
        k = tahmin.karne(cfg, con)
        md = tahmin.format_karne_md(k)
        assert "Henüz çözülmüş tahmin yok" in md
        assert "canlı isabet iddiası YOKTUR" in md
    finally:
        con.close()


# ------------------------------------------------------------ haftalık
def test_haftalik_rapor_arsiv_ilerlemesini_yaziyor(rapor_ortami):
    """STATE.md kapı tahminini buradan okuyor: "Gerçek ilerleme haftalık pazar
    raporundaki 'Arşiv İlerlemesi' satırından okunur — tahmin etme, rapordan oku."
    """
    cfg, _ = rapor_ortami
    con, _ = sentetik_db(cfg, gun=300, prim_gun=45)
    con.close()
    metin = report.build_weekly_report(cfg)
    assert "Arşiv İlerlemesi" in metin
    assert "45/60 gün" in metin
    assert "Haftanın Hareketi" in metin
    assert "🎯 HÜKÜM" in metin, "haftalık rapor günlük içeriği de taşımalı"


# ------------------------------------------------------------ kaydetme
def test_rapor_dosya_adi_ve_kaydi(rapor_ortami):
    cfg, kok = rapor_ortami
    con, _ = sentetik_db(cfg, gun=80, prim_gun=20)
    con.close()
    yol = report.save_report(cfg, "# test raporu\n")
    assert yol.endswith("rapor_2026-07-23.md")
    assert (kok / "reports" / "rapor_2026-07-23.md").exists()
    assert report.latest_report_path(cfg) == yol


def test_kaydedilen_raporda_chat_id_maskeleniyor(rapor_ortami, monkeypatch):
    """Repo public: commit'lenen hiçbir metinde chat_id görünmemeli (savunma
    katmanı — asıl koruma raporun onu hiç içermemesi)."""
    cfg, kok = rapor_ortami
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654321")
    con, _ = sentetik_db(cfg, gun=80, prim_gun=20)
    con.close()
    yol = report.save_report(cfg, "rapor · chat 987654321 · son")
    metin = util.abspath(yol).read_text(encoding="utf-8")
    assert "987654321" not in metin
    assert "<chat_id>" in metin


# ------------------------------------------------------------ Telegram
def test_telegram_duz_metne_cevirirken_sayilari_korur():
    """Rapor Telegram'a DÜZ METİN gidiyor (Markdown kaçış tuzağı yok). Süsler
    silinirken sayı/işaret kaybolursa kullanıcı yanlış rakam okur."""
    md = ("## 🎯 HÜKÜM\n**ÇEKİRDEK ALIM:** AZ AL  (0.75× normal alım)\n"
          "> Reel net mevduat %+12.7 → yüksek\n`banka_hesap` · fark **+3.19p**\n")
    duz = telegram_bot._md_to_plain(md)
    for parca in ("0.75×", "%+12.7", "+3.19p", "banka_hesap", "AZ AL"):
        assert parca in duz, f"{parca} kayboldu"
    assert "**" not in duz and "`" not in duz
    assert not duz.startswith("#") and "\n>" not in duz


def test_telegram_bolme_sinirlari_asmiyor_ve_icerik_kaybetmiyor():
    """4096 karakter sınırı: parçalar sınırın altında kalmalı ve birleştirildiğinde
    içerik (boşluk hariç) korunmalı — tablo/paragraf ortadan kesilmesin."""
    uzun = "\n".join(f"| satır {i} | değer {i * 3.14159:.4f} |" for i in range(600))
    parcalar = telegram_bot._chunks(uzun)
    assert len(parcalar) > 1
    for p in parcalar:
        assert len(p) <= telegram_bot.TG_LIMIT - 200
    birlesik = "".join(parcalar).replace("\n", "")
    assert birlesik == uzun.replace("\n", "")


def test_telegram_tek_satir_sinirdan_uzunsa_sert_boluyor():
    """Tek bir satır sınırdan uzunsa sonsuz döngüye girmemeli."""
    parcalar = telegram_bot._chunks("x" * 20000)
    assert len(parcalar) >= 4
    assert all(len(p) <= telegram_bot.TG_LIMIT - 200 for p in parcalar)
    assert "".join(parcalar) == "x" * 20000


def test_gercek_rapor_telegram_sinirina_bolunebiliyor(rapor_ortami):
    """Uçtan uca: gerçek rapor metni Telegram'a sığacak parçalara ayrılabilmeli."""
    cfg, _ = rapor_ortami
    metin = _rapor(cfg, prim_gun=70)
    parcalar = telegram_bot._chunks(telegram_bot._md_to_plain(metin))
    assert parcalar and all(len(p) <= telegram_bot.TG_LIMIT - 200 for p in parcalar)


def test_alarm_mesaji_uc_bilgiyi_tasiyor():
    """Rehber 6.3 şeması: gerekçe + geçersizlik + disclaimer. Geçersizlik koşulu
    olmayan bir alarm yanlışlanamaz — projenin dürüstlük kuralına aykırı."""
    from src import notify
    mesaj = notify._format_alert({
        "tip": "prim_sapma", "kural": "|prim| > %1.5", "deger": 2.0,
        "gerekce": "Prim %+2.00 teorik değerden saptı.",
        "gecersizlik": "Prim bandına dönerse geçersiz."})
    assert "Prim %+2.00" in mesaj
    assert "Geçersizlik" in mesaj
    assert "yatırım tavsiyesi değildir" in mesaj


# ---------- BİLDİRİM HATTI SAĞLIĞI (L-018) ----------
# Düzeltmenin üçüncü katmanı: hattın kırılmasını ÖNLEMEK yetmez, kırıldığında
# Mert'in GÖRMESİ gerekir. 2026-07-29 kesintisi 13 gün sürdü çünkü hiçbir çıktı
# "gönderemedim" demiyordu. Bu satır o sessizliği kapatır — dolayısıyla rapor
# sözleşmesinin parçasıdır, kozmetik değil.
def test_bildirim_hatti_saglikliyken_rapor_sessiz():
    assert report.bildirim_saglik_metni({}) == ""
    assert report.bildirim_saglik_metni({"ardisik_hata": 0}) == ""
    assert report.bildirim_saglik_metni(None) == ""


def test_bildirim_hatti_arizaliyken_rapor_BAGIRIR():
    m = report.bildirim_saglik_metni({
        "ardisik_hata": 37,
        "son_hata": "prim_sapma: HTTPError: 400 Client Error: Bad Request",
        "son_hata_utc": "2026-08-11T09:15:00+00:00"})
    assert m, "arıza varken satır boş olamaz"
    assert "37" in m, "kaç ardışık hata olduğu görünmeli"
    assert "GİTMİYOR" in m, "sonucun ne olduğu açıkça yazılmalı"
    assert "400" in m, "kök sebep metni görünmeli"
    assert "2026-08-11" in m, "ne zamandır sürdüğü görünmeli"


def test_bildirim_hatti_satiri_defter_yokken_patlamaz(tmp_path):
    """Defter okunamazsa rapor SESSİZ kalmalı — rapor üretimi bloklanmamalı."""
    cfg = {"alerts": {"state_file": str(tmp_path / "yok.json")}}
    assert report.bildirim_hatti_satiri(cfg) == ""


def test_bildirim_hatti_satiri_defterden_okur(tmp_path):
    import json
    p = tmp_path / "alert_state.json"
    p.write_text(json.dumps({"saglik": {"ardisik_hata": 5,
                                        "son_hata": "prim_sapma: HTTPError: 400",
                                        "son_hata_utc": "2026-08-11T09:00:00+00:00"}}),
                 encoding="utf-8")
    m = report.bildirim_hatti_satiri({"alerts": {"state_file": str(p)}})
    assert "5" in m and "GİTMİYOR" in m


def test_ariza_defteri_TAM_RAPORA_baglanmis(rapor_ortami):
    """KİLİT TEST (L-008: bir değer üretmek onu BAĞLAMAK değildir).

    `bildirim_saglik_metni` doğru string üretse bile `build_report` onu gövdeye
    koymuyorsa Mert için YOKTUR — 13 günlük kesintinin dersi tam buydu.
    """
    import json
    cfg, _ = rapor_ortami
    util.write_json(cfg["alerts"]["state_file"], {
        "last_sent": {}, "daily": {},
        "saglik": {"ardisik_hata": 42,
                   "son_hata": "prim_sapma: HTTPError: 400 Client Error: Bad Request",
                   "son_hata_utc": "2026-08-11T09:15:00+00:00"}})
    metin = _rapor(cfg, prim_gun=40)
    assert "BİLDİRİM HATTI ARIZALI" in metin, "arıza raporun gövdesine bağlanmamış"
    assert "42" in metin and "GİTMİYOR" in metin
    # Üstte olmalı: veri kalitesi dipnotuna gömülürse görülmez.
    assert metin.index("BİLDİRİM HATTI ARIZALI") < metin.index("## Veri Kalitesi")


def test_hat_saglikliyken_tam_rapor_uyari_basmiyor(rapor_ortami):
    """Yanlış alarm da bir arızadır: sağlıklı hatta uyarı çıkmamalı."""
    cfg, _ = rapor_ortami
    util.write_json(cfg["alerts"]["state_file"],
                    {"last_sent": {}, "daily": {}, "saglik": {"ardisik_hata": 0}})
    metin = _rapor(cfg, prim_gun=40)
    assert "BİLDİRİM HATTI ARIZALI" not in metin
