"""DEJENERE METRİK AVI — "girdiden bağımsız sabit çıkan alan ölçüm değil KİMLİKTİR" (L-010).

L-010 bu projenin en pahalı dersi: karne "tabana fark +0.0p · gram etkisi
+0.00%" yazıyordu ve bu gerçek bir ölçüm gibi okunuyordu. Ölçünce görüldü ki o
iki sayı **piyasa ne yaparsa yapsın** 0.00 çıkıyor (11 senaryoda doğrulandı) —
çünkü kayıtlı hükümlerin hiçbiri SAT değil ve `hukum_dogru_mu` SAT olmayan her
hükme tabanla aynı cevabı veriyor. Ekim'de yazılacak "trade kolu kalıcı kapalı"
ADR'si bir ölçüme değil bir totolojiye dayanacaktı.

Dersin kuralı bir SORU: **"Bu sayının farklı çıkabilmesi için ne olması
gerekir?"** Cevap üretilemiyorsa metrik değil kimlik yazılmıştır. Somut testi de
kural olarak veriyor: *"metriği uç senaryolarla besle; hepsinde aynı çıkıyorsa
ya girdi kümesi eksiktir ya formül dejenere."*

Bu dosya o testi her karar metriği için kurumsallaştırır. İki yön birlikte:

- **Ölçebilen metrik ÖLÇEBİLİYOR olmalı** (uç senaryolarda değer değişmeli)
- **Ölçemeyen durum ÖLÇEMEDİĞİNİ SÖYLEMELİ** (rakamla değil sebeple)
"""
from __future__ import annotations

import pytest

from src import calc, db, gram, karar, notify, signals, tahmin, util
from tests.conftest import cfg_kopya, sentetik_db

CFG = util.load_config()
RT = 1.20

# ADR #008-A'da kullanılan senaryo yelpazesi: −40% … +60% gram carry.
SENARYOLAR = [-40.0, -25.0, -10.0, -5.0, -1.0, 0.0, 1.0, 5.0, 10.0, 25.0, 60.0]


def _satir(hukum: str, kazanc: float) -> dict:
    """Çözülmüş bir tahmin satırı — üreticinin (`tahmin.cozumle`) yazdığı şekil."""
    return {"hukum": hukum,
            "hukum_dogru": 1 if gram.hukum_dogru_mu(hukum, kazanc, RT) else 0,
            "taban_dogru": 1 if gram.hukum_dogru_mu("TUT", kazanc, RT) else 0,
            "gram_etkisi_pct": tahmin.gram_etkisi(hukum, kazanc, RT)}


# ------------------------------------------------------- karne: kimlik vs ölçüm
def test_SAT_hukmu_olmayan_karne_11_senaryoda_AYNI_cikiyor():
    """KİLİT TEST — ADR #008-A'nın ölçümünün testi.

    Bu test GEÇMESİ gereken bir dejenerelik kanıtıdır: kayıtlı hükümler yalnız
    AL_*/TUT ise iki metrik piyasadan bağımsız olarak SABİTTİR. `olculebilir_mi`
    bayrağı işte bu yüzden var; bayrak kaldırılırsa bu testin gösterdiği
    totoloji gerçek bir ölçüm gibi raporlanmaya döner.
    """
    sonuclar = set()
    for kazanc in SENARYOLAR:
        satirlar = [_satir(h, kazanc) for h in ("AL_COK", "AL", "AL_AZ", "TUT")]
        k = tahmin.karne_ozeti(satirlar, zayif_n=30)
        sonuclar.add((round(k["isabet_farki_puan"], 6), round(k["gram_etkisi_pct"], 6)))
        assert k["olculebilir_mi"] is False
        assert k["sat_hukum_sayisi"] == 0
    assert sonuclar == {(0.0, 0.0)}, (
        f"beklenen kimlik bozuldu: {sonuclar} — eğer artık ölçüm üretiyorsa "
        "`olculebilir_mi` mantığı gözden geçirilmeli")


def test_SAT_hukmu_olan_karne_senaryoya_gore_DEGISIYOR():
    """Karşı kontrol: metrik bilgi taşıyabiliyor mu?

    Yukarıdaki test tek başına "formül bozuk" ile "girdi eksik" ayrımını
    yapamaz. Bu test ayrımı yapıyor: SAT hükmü eklendiği an aynı senaryo
    yelpazesi FARKLI sonuçlar üretiyor → sorun formülde değil, girdi
    kümesinde (kapı kapalı olduğu için sistem SAT üretemiyor).
    """
    farkli_etki, farkli_isabet = set(), set()
    for kazanc in SENARYOLAR:
        satirlar = [_satir("SAT_25", kazanc), _satir("TUT", kazanc)]
        k = tahmin.karne_ozeti(satirlar, zayif_n=30)
        assert k["olculebilir_mi"] is True
        farkli_etki.add(round(k["gram_etkisi_pct"], 6))
        farkli_isabet.add(round(k["isabet_farki_puan"], 6))
    assert len(farkli_etki) == len(SENARYOLAR), "gram etkisi senaryoya duyarsız"
    assert len(farkli_isabet) > 1, "isabet farkı senaryoya duyarsız"


def test_karne_olculebilirlik_bayragi_tam_olarak_SAT_varligina_bagli():
    """Bayrak başka bir şeye bağlanırsa (ör. N eşiğine) anlamını yitirir."""
    for hukumler, beklenen in (
            (["TUT"], False), (["AL"], False), (["AL_COK", "TUT"], False),
            (["SAT_25"], True), (["TUT", "SAT_50"], True)):
        k = tahmin.karne_ozeti([_satir(h, 5.0) for h in hukumler], zayif_n=30)
        assert k["olculebilir_mi"] is beklenen, hukumler
        assert (k["sat_hukum_sayisi"] > 0) is beklenen


def test_bos_karne_olcum_iddia_etmiyor():
    k = tahmin.karne_ozeti([], zayif_n=30)
    assert k["cozulmus"] == 0
    assert k["olculebilir_mi"] is False and k["yeterli_mi"] is False


def test_gram_etkisi_toplamsal_bilesik_degil():
    """Pozisyonun tamamı her seferinde işleme girmiyor (oranlı giriyor) → toplam
    bileşik değil toplamsal. Bileşiğe çevrilirse küçük etkiler abartılır."""
    satirlar = [_satir("SAT_25", 10.0), _satir("SAT_25", -10.0)]
    k = tahmin.karne_ozeti(satirlar, zayif_n=1)
    assert k["gram_etkisi_pct"] == pytest.approx(
        sum(s["gram_etkisi_pct"] for s in satirlar))


# ------------------------------------------------------- kapı gerekçeleri
def test_kapi_dort_kapali_durumu_AYRI_gerekce_veriyor():
    """KİLİT TEST. Ekim'deki kapı kararı bu gerekçe metnine bakacak.

    Dört farklı sebep aynı cümleyi verirse karar "ölçtük ve olmadı" ile
    "ölçemedik" arasındaki farkı göremez — ADR #008'in bulduğu tam bu.
    """
    kapali_config = karar.kapi_durumu(cfg_kopya(**{"karar.taktik.aktif": False}), None)
    az_n = karar.kapi_durumu(cfg_kopya(**{"karar.taktik.aktif": True}),
                             {"cozulmus": 5, "olculebilir_mi": False})
    olcumsuz = karar.kapi_durumu(cfg_kopya(**{"karar.taktik.aktif": True}),
                                 {"cozulmus": 50, "gram_etkisi_pct": 0.0,
                                  "isabet_farki_puan": 0.0, "olculebilir_mi": False,
                                  "sat_hukum_sayisi": 0})
    olumsuz = karar.kapi_durumu(cfg_kopya(**{"karar.taktik.aktif": True}),
                                {"cozulmus": 50, "gram_etkisi_pct": -1.0,
                                 "isabet_farki_puan": 20.0, "olculebilir_mi": True,
                                 "sat_hukum_sayisi": 12})
    gerekceler = [d["gerekce"] for d in (kapali_config, az_n, olcumsuz, olumsuz)]
    assert len(set(gerekceler)) == 4, f"gerekçeler ayrışmıyor: {gerekceler}"
    assert all(d["acik"] is False for d in (kapali_config, az_n, olcumsuz, olumsuz))
    # ölçülemezlik "şart sağlanmadı" gibi okunmamalı
    assert "ölçülmedi" in olcumsuz["gerekce"]
    assert "ölçülmedi" not in olumsuz["gerekce"]
    assert olcumsuz["olculebilir"] is False and olumsuz["olculebilir"] is True


def test_kapi_acilabiliyor_da():
    """Kapının açılabildiği de kanıtlanmalı: hiçbir girdiyle açılamayan bir kapı
    "şartı sağlayınca açılır" cümlesini yalan yapar (L-010'un kapı hâli)."""
    acik = karar.kapi_durumu(cfg_kopya(**{"karar.taktik.aktif": True}),
                             {"cozulmus": 50, "gram_etkisi_pct": 2.0,
                              "isabet_farki_puan": 15.0, "olculebilir_mi": True,
                              "sat_hukum_sayisi": 21})
    assert acik["acik"] is True and "şart sağlandı" in acik["gerekce"]


# ------------------------------------------------------- çekirdek kol
def _cek_esik(aktif: bool):
    """Çekirdek eşikleri, kademe kapısı açık/kapalı. ADR #012'de kademe ÜRETİMDE
    kapatıldı; mekanizmanın kendisi silinmedi, kapıya bağlandı. Bu testler
    mekanizmayı `aktif=True` ile denetlemeye devam eder — kapı bir gün yeniden
    açılırsa dejenerelik koruması hâlâ yürürlükte olsun."""
    e = dict(CFG["karar"]["cekirdek"])
    e["kademe_aktif"] = aktif
    return e


def test_cekirdek_kol_girdiye_gercekten_duyarli():
    """Çekirdek kol tek kapı değişkeni okuyor; formül dejenere olsa (ör. eşik
    karşılaştırması ters kurulsa) hep AL dönerdi ve kimse fark etmezdi."""
    esik = _cek_esik(True)
    hukumler = {karar.cekirdek_hukum(r, esik)["hukum"]
                for r in (-30.0, -5.0, -0.1, 0.5, 5.0, 9.9, 10.5, 30.0)}
    assert hukumler == {karar.AL_COK, karar.AL, karar.AL_AZ}, hukumler
    carpanlar = {karar.cekirdek_hukum(r, esik)["carpan"] for r in (-5.0, 5.0, 30.0)}
    assert len(carpanlar) == 3, "kademe çarpanı girdiye duyarsız"


def test_cekirdek_kol_eşik_siniri_keskin():
    """Sınır davranışı belirsizse aynı gün iki kez koşan iş farklı hüküm
    üretebilir (kayıt değiştirilemez olduğu için bu kalıcı tutarsızlık olurdu)."""
    esik = _cek_esik(True)
    dusuk, yuksek = esik["reel_mevduat_dusuk_pct"], esik["reel_mevduat_yuksek_pct"]
    assert karar.cekirdek_hukum(dusuk - 1e-9, esik)["hukum"] == karar.AL_COK
    assert karar.cekirdek_hukum(dusuk, esik)["hukum"] == karar.AL
    assert karar.cekirdek_hukum(yuksek, esik)["hukum"] == karar.AL
    assert karar.cekirdek_hukum(yuksek + 1e-9, esik)["hukum"] == karar.AL_AZ


# ---- Kademe KAPALI iken: eylem düz, TEŞHİS hâlâ duyarlı (ADR #012) ----
def test_kademe_kapaliyken_alim_plani_HIC_degismez():
    """KİLİT: kapatmanın tek amacı bu — ölçülmemiş bir kural alımı geciktirmesin.

    Ölçüm (ADR #012): kural ateşlendiğinde ertelemenin ortalama gram kazancı
    %-0.64 (N=22, t=1.03), başa baş 0.00'ın ALTINDA; canlı doğrulamada
    07-27 → 08-10 arası kademe -%1.55 gram götürdü.
    """
    esik = _cek_esik(False)
    for r in (-30.0, -5.0, -0.1, 0.0, 5.0, 9.9, 10.5, 30.0, 12.85):
        h = karar.cekirdek_hukum(r, esik)
        assert h["carpan"] == 1.0, f"reel={r}: kademe kapalıyken çarpan 1.0 olmalı"
        assert h["hukum"] == karar.AL, f"reel={r}: kapalıyken hüküm AL olmalı"


def test_kademe_kapaliyken_TESHIS_hala_girdiye_duyarli():
    """Eylem düzleşti ama kural GÖRÜNÜR kalmalı — "yapmadım" ile "yapacak bir
    şey yoktu" ayrı şeylerdir. Kural adı sessizleşirse kapatma kararı da
    denetlenemez hâle gelir."""
    esik = _cek_esik(False)
    kurallar = {karar.cekirdek_hukum(r, esik)["kural"]
                for r in (-5.0, 5.0, 30.0)}
    assert len(kurallar) == 3, f"kademe kapalıyken teşhis körleşti: {kurallar}"
    yuksek = karar.cekirdek_hukum(30.0, esik)
    metin = " ".join(yuksek["gerekce"])
    assert "KAPALI" in metin and "ADR #012" in metin, "kapatma sebebi yazılmamış"
    assert "0.75" in metin, "kademe açık olsaydı ne olacağı yazılmamış"
    assert yuksek["kademe_olurdu"] == 0.75


# ------------------------------------------------------- taktik kol
def _ufuk_engel(beklenen=None, ver_beklenen=False):
    u = {"gun": 21, "n_bagimsiz": 121, "taban_ortalama_pct": -1.99,
         "kazanma_pct": 36.0, "maliyet_sonrasi_kazanma_pct": 28.0,
         "en_kotu_pct": -36.2, "taktik_esik_puan": 3.19, "cekirdek_esik_puan": 1.99}
    if ver_beklenen:
        u["beklenen_gram_kazanc_pct"] = beklenen
    return u


def test_taktik_kol_SAT_uretebiliyor_ama_yalnizca_kapi_ve_uretici_varken():
    """SAT dalı ERİŞİLEBİLİR olmalı — erişilemez bir dal ölü koddur ve "kapı
    açılırsa satarım" cümlesini yalan yapar. Üç şart birlikte gerekli:
    kapı açık + üretici bağlı + beklenen kazanç eşiği aşıyor."""
    acik = {"acik": True, "gerekce": ""}
    kapali = {"acik": False, "gerekce": "test"}
    assert karar.taktik_hukum(_ufuk_engel(6.0, True), acik, 1.5)["hukum"] == karar.SAT_25
    assert karar.taktik_hukum(_ufuk_engel(4.0, True), acik, 1.5)["hukum"] == karar.TUT
    assert karar.taktik_hukum(_ufuk_engel(6.0, True), kapali, 1.5)["hukum"] == karar.TUT
    assert karar.taktik_hukum(_ufuk_engel(), acik, 1.5)["hukum"] == karar.TUT


def test_uretimdeki_engel_sekliyle_SAT_uretilemiyor_ve_sebebi_yaziliyor():
    """ADR #008-C: `beklenen_gram_kazanc_pct` üreticisi YOK ve bu bir unutma
    değil ölçüm sonucu. Kod "hesaplanamadı" ile "üretici bağlı değil"i
    AYIRMALI; ayırmazsa ölü dal "bugün sinyal zayıf" gibi okunur."""
    r = karar.taktik_hukum(_ufuk_engel(), {"acik": True, "gerekce": ""}, 1.5)
    assert r["hukum"] == karar.TUT
    assert r["beklenen_kaynak"] == "uretici_yok"
    olculdu = karar.taktik_hukum(_ufuk_engel(1.0, True),
                                 {"acik": True, "gerekce": ""}, 1.5)
    assert olculdu["beklenen_kaynak"] == "olculdu"
    assert r["gerekce"] != olculdu["gerekce"]


def test_emniyet_carpani_gercekten_etkili():
    """Çarpan dejenere olsa (ör. hep 1.0 kullanılsa) eşik sessizce %50 düşerdi."""
    acik = {"acik": True, "gerekce": ""}
    beklenen = 3.19 * 1.2                                  # 1.0'ı aşar, 1.5'i aşmaz
    assert karar.taktik_hukum(_ufuk_engel(beklenen, True), acik, 1.0)["hukum"] == \
        karar.SAT_25
    assert karar.taktik_hukum(_ufuk_engel(beklenen, True), acik, 1.5)["hukum"] == \
        karar.TUT


# ------------------------------------------------------- eşikler config'ten
@pytest.mark.parametrize("alan,esik_yolu,tetikleyen", [
    ("prim", "alerts.prim_abs_pct", 3.0),
    ("prim_z", "alerts.prim_z", 4.0),
    ("quarter_z", "alerts.quarter_z", 4.0),
])
def test_esik_configten_okunuyor_koda_gomulu_degil(alan, esik_yolu, tetikleyen):
    """KİLİT TEST — anti-hardcoding.

    Eşiği config'te İKİ KATINA çıkarınca alarm SUSMALI. Susmuyorsa değer koda
    gömülmüş ve `config.yaml`'ın ilk satırındaki kural ("kod içine sabit
    gömülmez") çiğnenmiş demektir — kullanıcı config'i değiştirip hiçbir şeyin
    değişmediğini görür.
    """
    ctx = {"all_fresh": True, alan: tetikleyen}
    normal = notify.evaluate_thresholds(ctx, CFG)
    assert normal, f"{alan} tetiklenmedi (test kurgusu bozuk)"
    yuksek = cfg_kopya(**{esik_yolu: tetikleyen * 2})
    assert not notify.evaluate_thresholds(ctx, yuksek), (
        f"{esik_yolu} iki katına çıktı ama alarm hâlâ tetikleniyor")


def test_gunluk_hareket_esigi_atr_carpanina_duyarli():
    ctx = {"all_fresh": True, "daily_move": 100.0, "atr": 40.0}
    assert notify.evaluate_thresholds(ctx, cfg_kopya(**{"alerts.daily_move_atr": 2.0}))
    assert not notify.evaluate_thresholds(ctx, cfg_kopya(**{"alerts.daily_move_atr": 3.0}))


def test_makas_persentili_duyarli():
    ctx = {"all_fresh": True, "spread": 0.5, "spread_p90": 0.4}
    assert notify.evaluate_thresholds(ctx, CFG)
    assert not notify.evaluate_thresholds({**ctx, "spread_p90": 0.6}, CFG)


def test_gunluk_tavan_ve_sogumanin_ikisi_de_etkili():
    """Bildirim yorgunluğu koruması: ikisi de dejenere olmamalı."""
    alarmlar = [{"tip": f"t{i}", "kural": "k", "deger": 1, "gerekce": "g",
                 "gecersizlik": "x"} for i in range(10)]
    gonderilecek, _ = notify.apply_cooldown(alarmlar, {}, "2026-07-23T10:00:00+00:00",
                                            24, 6)
    assert len(gonderilecek) == 6, "günlük tavan uygulanmıyor"
    durum = {"last_sent": {"t0": "2026-07-23T09:00:00+00:00"}, "daily": {}}
    ikinci, _ = notify.apply_cooldown(alarmlar[:1], durum,
                                      "2026-07-23T10:00:00+00:00", 24, 6)
    assert ikinci == [], "soğuma uygulanmıyor"


# ------------------------------------------------------- kuru prova
def test_kuru_prova_iki_tabani_AYIRT_EDEBILIYOR(izole_kok, ag_kapali):
    """ADR #006-B'nin varlık sebebi: kapı GÜN sayıyor ama z TÜM KAYITLAR
    üzerinden hesaplanıyor. Prova ilk günden bunu ölçtü (kayıt +0.92 · gün +1.36).

    İki taban aynı formüle indirilirse prova hiçbir şey ölçmez ve Eylül'deki
    taban kararı dayanaksız kalır — bu test o çöküşü yakalar.
    """
    cfg, _ = izole_kok
    con, _ = sentetik_db(cfg, gun=90, prim_gun=60, prim_ornek=4)
    try:
        olcum = signals.zscore_dry_run(cfg, con)
        assert olcum["z_kayit_tabani"] is not None
        assert olcum["z_gun_tabani"] is not None
        assert olcum["z_kayit_tabani"] != olcum["z_gun_tabani"], (
            "iki taban aynı sonucu veriyor → prova ölçüm içermiyor")
        assert olcum["std_kayit"] != olcum["std_gun"]
        assert olcum["n_kayit"] > olcum["n_gun"], "gün tabanı kayıtları ortalamıyor"
        assert olcum["gun"] == 60 and olcum["esik_gun"] == 60
    finally:
        con.close()


def test_kuru_prova_kapi_kapaliyken_de_olcuyor(izole_kok, ag_kapali):
    """Provanın tek amacı kapı AÇILMADAN dağılımı öğrenmek; kapıya tabi olursa
    hiç ölçmez ve Eylül'de ilk kez kalibrasyonsuz ateşlenir."""
    cfg, _ = izole_kok
    con, _ = sentetik_db(cfg, gun=40, prim_gun=25, prim_ornek=3)
    try:
        olcum = signals.zscore_dry_run(cfg, con)
        assert olcum["kapi_acik"] is False
        assert olcum["z_kayit_tabani"] is not None, "kapı kapalıyken ölçüm yapılmıyor"
    finally:
        con.close()


def test_zscore_yetersiz_veride_sayi_uydurmuyor():
    """Kapı kapalıyken `calc.zscore` None döner — uydurma bir z, alarmı
    kalibrasyonsuz ateşler."""
    assert calc.zscore([1.0, 2.0, 3.0], 5.0, 60).value is None
    assert calc.zscore([1.0, 2.0, 3.0], 5.0, 60).status == "insufficient"


# ------------------------------------------------------- panel paydası
def test_veri_yok_gostergesi_paydadan_dusuyor():
    """Eksik gösterge 0 (nötr) sayılırsa uzlaşı skoru sulandırılır: 6/7 gösterge
    ile karar vermek ile 7/7 ile karar vermek aynı görünürdü."""
    from src.indicators import NOTR, OLUMLU, Signal, YOK, consensus
    dolu = consensus([Signal("a", OLUMLU, ""), Signal("b", OLUMLU, "")])
    eksikli = consensus([Signal("a", OLUMLU, ""), Signal("b", OLUMLU, ""),
                         Signal("c", YOK, "")])
    assert dolu == eksikli, "veri yok göstergesi paydaya girmiş"
    assert consensus([Signal("a", YOK, "")]) == {"score": 0, "n": 0,
                                                "yon": NOTR, "normalized": 0.0}


def test_uzlasi_yonu_gercekten_degisiyor():
    from src.indicators import NOTR, OLUMLU, OLUMSUZ, Signal, consensus
    assert consensus([Signal("a", OLUMLU, "")] * 3)["yon"] == OLUMLU
    assert consensus([Signal("a", OLUMSUZ, "")] * 3)["yon"] == OLUMSUZ
    assert consensus([Signal("a", OLUMLU, ""), Signal("b", OLUMSUZ, "")])["yon"] == NOTR


# ---------------------------------------------------------------------------
# REJİM SİNYALİ — tek sınıfa çökmüş sınıflandırıcı "ölçüm" iddia edemez
# (denetim 2026-08-28, B-14). Aynı ders L-010, farklı metrik: rapor 48/48 gün
# "Bu rejim 2016'dan beri 40 gün; medyan +10.6%, kazanma %82" bastı ve bu satır
# `_baseline` (tüm günler) satırıyla BİREBİR aynıydı — FRED DFII10 ölü olduğu
# için `regime_label` 2585/2585 güne "X" veriyordu. Tabanın kopyasını rejim
# ölçümü diye sunmak, farkı sıfır olan bir kenar iddiasıdır.
# ---------------------------------------------------------------------------

def test_tek_sinifli_rejim_olcum_iddia_etmiyor(izole_kok, ag_kapali, monkeypatch):
    """FRED ölüyken sınıflandırıcı tek sınıfa çöker → sinyal 'ölçemedim' demeli."""
    from src import backtest as bt

    cfg, _ = izole_kok
    con, _ = sentetik_db(cfg, gun=400)
    monkeypatch.setattr(bt, "_fred_aligned",
                        lambda c, dates: [None] * len(dates))
    try:
        # tetikleyicinin gerçekten kurulduğunu doğrula (yoksa test vacuous geçer)
        hist = [dict(r) for r in signals._history(con)]
        labels = bt._label_regimes(cfg, hist, [None] * len(hist))
        assert len(set(labels)) == 1, "kurgu dejenere sınıflandırıcı üretmedi"

        regime, rstat = signals._current_regime(cfg, con)
        assert regime is None and rstat is None, (
            "tek sınıflı sınıflandırıcı rejim ölçümü döndürdü — döndürülen "
            "etiket tüm veriyi kapsıyor, yani tabanın kendisi")
    finally:
        con.close()


def test_dejenere_rejimde_rejim_satiri_SEBEP_yaziyor():
    """Satırı sessizce düşürmek 'ölçemedim' ile 'bir şey çıkmadı'yı aynı yapar.

    Yapısal denetim: `_current_regime` None döndüğünde `build_signals` bir
    rejim satırı üretmeli ve sebebi yazmalı. (Ağ bağımlı panel bacakları
    yüzünden tüm sinyal hattını koşturmak yerine kaynak sözleşmesi denetlenir —
    aynı kalıp `test_yapisal_korumalar.py`'de de kullanılıyor.)
    """
    kaynak = util.abspath("src/signals.py").read_text(encoding="utf-8")
    i = kaynak.find("regime, rstat = _current_regime")
    assert i > 0, "rejim sinyali kurulumu bulunamadı"
    blok = kaynak[i:i + 900]
    assert "if not regime:" in blok, (
        "rejim None iken satır sessizce düşüyor — 'ölçemedim' basılmıyor")
    assert "FRED" in blok, "sessiz düşüşün yerine geçen satır sebebi yazmıyor"


def test_rejim_koprusu_gun_ile_pencereyi_KARISTIRMIYOR():
    """`n` örtüşmeyen pencere sayısıdır; 'gün' diye basmak N'i 60× küçük gösterir."""
    kaynak = util.abspath("src/signals.py").read_text(encoding="utf-8")
    i = kaynak.find("Bu rejim 2016'dan beri")
    assert i > 0, "rejim köprü cümlesi bulunamadı"
    cumle = kaynak[i:i + 260]
    assert "örtüşmeyen" in cumle, (
        "rejim köprüsü pencere sayısını 'gün' diye sunuyor (B-10)")
