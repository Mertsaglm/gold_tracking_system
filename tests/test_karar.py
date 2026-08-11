"""Karar motoru saf çekirdek testleri.

En kritik test: `test_kapi_kapaliyken_en_guclu_sinyal_bile_tut`. Bu projede
kalibre edilmemiş bir kolun canlıda ilk kez ateşlenmesi somut bir risk — prim
z-skoru kapısı tam da bu yüzden `zscore_dry_run` ile provaya alınmıştı. Taktik
kol gerçek para yakabileceği için kapı kuralı testle kilitlenir: kapı kapalıyken
hiçbir girdi kombinasyonu SAT üretemez.
"""
import pytest

from src import karar, util

CFG = util.load_config()
ESIK = CFG["karar"]["cekirdek"]


def _cfg(**taktik):
    """config kopyası — testler gerçek config'i bozmasın."""
    import copy
    c = copy.deepcopy(CFG)
    c["karar"]["taktik"].update(taktik)
    return c


# `gram.engel_ozet`'in GERÇEKTEN ürettiği anahtar kümesi. Elle yazılmış bir
# fixture bir zamanlar buraya `beklenen_gram_kazanc_pct` de koyuyordu; üretici
# o anahtarı hiç üretmediği için "SAT dalı çalışıyor" diyen test yeşil geçiyor,
# üretimde ise dal ERİŞİLEMEZ kalıyordu. Fixture artık üreticinin şemasına
# bağlı ve sapma `test_engel_ozet_sozlesmesi` ile yakalanıyor.
_ENGEL_ALANLARI = ("gun", "n_bagimsiz", "taban_ortalama_pct", "kazanma_pct",
                   "maliyet_sonrasi_kazanma_pct", "en_kotu_pct",
                   "taktik_esik_puan", "cekirdek_esik_puan")

_YOK = object()          # "bu argüman hiç geçilmedi" işareti


def _engel(taban=-1.99, esik=3.19, beklenen=_YOK):
    """Üretimdeki `engel_ozet` çıktısının birebir şekli.

    `beklenen` GEÇİLMEZSE anahtar hiç konmaz — üretimdeki durum budur.
    Açıkça geçilirse (kapı-açık senaryolarını sınamak için) eklenir.
    """
    u = {"gun": 21, "n_bagimsiz": 121, "taban_ortalama_pct": taban,
         "kazanma_pct": 36.0, "maliyet_sonrasi_kazanma_pct": 28.0,
         "en_kotu_pct": -36.2,
         "taktik_esik_puan": esik, "cekirdek_esik_puan": abs(taban)}
    assert set(u) == set(_ENGEL_ALANLARI)
    if beklenen is not _YOK:
        u["beklenen_gram_kazanc_pct"] = beklenen
    return {"ufuklar": {CFG["karar"]["birincil_ufuk"]: u}}


# ---------- çekirdek kol ----------
def test_cekirdek_reel_faiz_negatifse_cok_al():
    r = karar.cekirdek_hukum(-3.0, ESIK)
    assert r["hukum"] == karar.AL_COK
    assert r["carpan"] == ESIK["kademe_carpani_ust"]


def test_cekirdek_reel_faiz_yuksekse_az_al():
    r = karar.cekirdek_hukum(12.7, ESIK)
    assert r["hukum"] == karar.AL_AZ
    assert r["carpan"] == ESIK["kademe_carpani_alt"]


def test_cekirdek_ara_bantta_normal():
    r = karar.cekirdek_hukum(5.0, ESIK)
    assert r["hukum"] == karar.AL
    assert r["carpan"] == 1.0


def test_cekirdek_veri_yoksa_plana_dokunma():
    """EVDS düşerse düzenli alım planı değişmez — sessiz bozulma yok."""
    r = karar.cekirdek_hukum(None, ESIK)
    assert r["hukum"] == karar.AL and r["carpan"] == 1.0


def test_cekirdek_hicbir_zaman_bekle_demez():
    """Çekirdek kol alımı KESMEZ, yalnız şiddetini ayarlar. t≈1.4'lük bir
    kanıtla 'bu ay hiç alma' demek savunulamaz."""
    for reel in (-50.0, -1.0, 0.0, 9.9, 10.1, 80.0, None):
        assert karar.cekirdek_hukum(reel, ESIK)["hukum"] != karar.BEKLE


def test_cekirdek_kademeler_dar():
    """Kademe 2x/0.5x DEĞİL — kanıt gücüyle orantılı."""
    assert 1.0 < ESIK["kademe_carpani_ust"] <= 1.5
    assert 0.5 <= ESIK["kademe_carpani_alt"] < 1.0


# ---------- kapı ----------
def test_kapi_config_kapaliysa_kapali():
    assert karar.kapi_durumu(_cfg(aktif=False), None)["acik"] is False


def test_kapi_aktif_ama_karne_yoksa_kapali():
    assert karar.kapi_durumu(_cfg(aktif=True), None)["acik"] is False


def test_kapi_yetersiz_cozulmus_kapali():
    k = {"cozulmus": 5, "gram_etkisi_pct": 3.0, "isabet_farki_puan": 20.0,
         "olculebilir_mi": True, "sat_hukum_sayisi": 3}
    assert karar.kapi_durumu(_cfg(aktif=True), k)["acik"] is False


def test_kapi_gram_etkisi_negatifse_kapali():
    """İsabet yüksek ama gram etkisi negatifse kapı AÇILMAZ — amaç fonksiyonu
    isabet değil, gram."""
    k = {"cozulmus": 50, "gram_etkisi_pct": -1.0, "isabet_farki_puan": 20.0,
         "olculebilir_mi": True, "sat_hukum_sayisi": 18}
    assert karar.kapi_durumu(_cfg(aktif=True), k)["acik"] is False


def test_kapi_tum_sartlar_saglanirsa_acik():
    # `olculebilir_mi` ŞART: gram etkisi +2.0 ancak SAT hükümleri varsa oluşabilir.
    k = {"cozulmus": 50, "gram_etkisi_pct": 2.0, "isabet_farki_puan": 15.0,
         "olculebilir_mi": True, "sat_hukum_sayisi": 21}
    assert karar.kapi_durumu(_cfg(aktif=True), k)["acik"] is True


# ---------- taktik kol: kapı kuralı ----------
def test_kapi_kapaliyken_en_guclu_sinyal_bile_tut():
    """KİLİT TEST. Kapı kapalıyken hiçbir beklenen kazanç SAT üretemez."""
    kapali = {"acik": False, "gerekce": "test"}
    for beklenen in (0.0, 5.0, 50.0, 1000.0):
        e = _engel(beklenen=beklenen)["ufuklar"][CFG["karar"]["birincil_ufuk"]]
        r = karar.taktik_hukum(e, kapali, 1.5)
        assert r["hukum"] == karar.TUT
        assert r["kapi_acik"] is False


def test_kapi_kapali_gerekce_olculen_sayilari_tasir():
    """Hüküm gerekçesi ölçüme dayanmalı — 'çünkü öyle' kabul edilmez."""
    e = _engel()["ufuklar"][CFG["karar"]["birincil_ufuk"]]
    g = " ".join(karar.taktik_hukum(e, {"acik": False, "gerekce": "x"}, 1.5)["gerekce"])
    assert "-1.99" in g and "3.19" in g and "N=121" in g


def test_kapi_acik_ama_maliyeti_asmazsa_tut():
    """Emniyet çarpanı: 3.19 × 1.5 = 4.785. Beklenen 4.0 yetmez."""
    e = _engel(beklenen=4.0)["ufuklar"][CFG["karar"]["birincil_ufuk"]]
    assert karar.taktik_hukum(e, {"acik": True, "gerekce": ""}, 1.5)["hukum"] == karar.TUT


def test_kapi_acik_ve_maliyeti_asarsa_sat():
    e = _engel(beklenen=6.0)["ufuklar"][CFG["karar"]["birincil_ufuk"]]
    assert karar.taktik_hukum(e, {"acik": True, "gerekce": ""}, 1.5)["hukum"] == karar.SAT_25


def test_taktik_engel_olcumu_yoksa_tut():
    assert karar.taktik_hukum(None, {"acik": True, "gerekce": ""}, 1.5)["hukum"] == karar.TUT


# ---------- birleşik ----------
def test_karar_ver_iki_kol_da_uretir():
    k = karar.karar_ver({"reel_net_mevduat": 12.7}, _cfg(aktif=False), _engel())
    assert k["cekirdek"]["hukum"] == karar.AL_AZ
    assert k["taktik"]["hukum"] == karar.TUT
    assert k["kapi"]["acik"] is False


def test_karar_ver_engelsiz_de_cokmez():
    """Ölçüm önbelleği yoksa (ilk kurulum) rapor yine de hüküm vermeli."""
    k = karar.karar_ver({"reel_net_mevduat": None}, _cfg(aktif=False), None)
    assert k["cekirdek"]["hukum"] == karar.AL
    assert k["taktik"]["hukum"] == karar.TUT


def test_format_ilk_satirda_hukum_var():
    """DoD: raporun ilk ekranında iki hüküm görünmeli."""
    md = karar.format_karar_md(
        karar.karar_ver({"reel_net_mevduat": 12.7}, _cfg(aktif=False), _engel()))
    ilk = md.split("\n")[:6]
    assert any("ÇEKİRDEK ALIM" in s for s in ilk)
    assert any("TAKTİK" in s for s in ilk)


def test_format_kapi_durumunu_yazar():
    md = karar.format_karar_md(
        karar.karar_ver({"reel_net_mevduat": 1.0}, _cfg(aktif=False), _engel()))
    assert "SAT kapısı: KAPALI" in md


# ---------- ÜRETİCİ ↔ TÜKETİCİ SÖZLEŞMESİ (bu sınıf hatanın tekrarını engeller) ----------
def test_engel_ozet_sozlesmesi_fixture_ile_ayni():
    """`gram.engel_ozet` ne üretiyorsa fixture da onu üretmeli.

    Fixture üreticiden ayrıştığı an, ona dayanan bütün karar testleri
    gerçekliğini kaybeder — `beklenen_gram_kazanc_pct` tam olarak böyle oldu.
    """
    from src import gram
    sahte_engel = {"ilk": "2016-01-04", "son": "2026-07-24", "n_gun": 2561,
                   "ufuklar": {"1ay": {"gun": 21, "n_bagimsiz": 121,
                                       "ortalama": -1.99, "kazanma_pct": 36.0,
                                       "maliyet_sonrasi_kazanma_pct": 28.0,
                                       "en_kotu": -36.2, "yeterli": True}}}
    ozet = gram.engel_ozet(CFG, sahte_engel)
    assert set(ozet["ufuklar"]["1ay"]) == set(_ENGEL_ALANLARI)


def test_uretici_beklenen_gram_kazancini_URETMIYOR():
    """Bu bir arıza değil, ÖLÇÜM SONUCU (ADR #007-H: 14 aday, hiçbiri geçmedi).

    Test bunu kilitliyor: bir gün gerçek bir tahminci bağlanırsa bu test
    düşecek ve o an `taktik_hukum`'un "üretici yok" dalının kaldırılması
    gerektiği hatırlatılacak.
    """
    from src import gram
    engel = gram.engel_oku(CFG)
    if engel is None:
        pytest.skip("gram_engeli.json yok")
    for ad, u in engel["ufuklar"].items():
        assert "beklenen_gram_kazanc_pct" not in u, (
            f"{ad}: üretici bağlanmış → karar.taktik_hukum'daki 'uretici_yok' "
            "dalı gözden geçirilmeli")


def test_uretici_yoksa_kapi_acik_olsa_bile_SAT_yok():
    """K-2: üretimdeki engel şekliyle SAT dalı erişilemez — ve bunu SÖYLER."""
    e = _engel()["ufuklar"][CFG["karar"]["birincil_ufuk"]]      # anahtar YOK
    r = karar.taktik_hukum(e, {"acik": True, "gerekce": ""}, 1.5)
    assert r["hukum"] == karar.TUT
    assert r["beklenen_kaynak"] == "uretici_yok"
    g = " ".join(r["gerekce"])
    assert "ÜRETİCİSİ BAĞLI DEĞİL" in g
    assert "hesaplanamadı" not in g, "üretici yokluğu 'hesaplanamadı' gibi okunmamalı"


def test_uretici_yok_ile_esigin_altinda_ayri_gerekce_verir():
    """İkisi aynı cümleyle raporlanırsa ölü kod 'zayıf sinyal' gibi okunur."""
    yok = karar.taktik_hukum(_engel()["ufuklar"][CFG["karar"]["birincil_ufuk"]],
                             {"acik": True, "gerekce": ""}, 1.5)
    altinda = karar.taktik_hukum(_engel(beklenen=1.0)["ufuklar"][CFG["karar"]["birincil_ufuk"]],
                                 {"acik": True, "gerekce": ""}, 1.5)
    assert yok["hukum"] == altinda["hukum"] == karar.TUT
    assert yok["beklenen_kaynak"] != altinda["beklenen_kaynak"]
    assert yok["gerekce"] != altinda["gerekce"]


# ---------- K-1: kapı totolojiden "şart sağlanmadı" sonucu ÇIKARMAMALI ----------
def test_kapi_olculemez_karneden_sart_saglanmadi_DEMEZ():
    """KİLİT TEST (ADR #008).

    Hiç SAT hükmü olmayan bir karnede gram etkisi ve isabet farkı yapısal olarak
    0.00'dır. Eski kod bunu "gram etkisi pozitif değil" diye raporluyordu — yani
    ölçülmemiş bir şeyi ölçülmüş-ve-olumsuz gibi gösteriyordu. Ekim'deki
    "trade kolu kalıcı kapalı" ADR'si bu cümleye dayanacaktı.
    """
    k = {"cozulmus": 50, "gram_etkisi_pct": 0.0, "isabet_farki_puan": 0.0,
         "olculebilir_mi": False, "sat_hukum_sayisi": 0}
    d = karar.kapi_durumu(_cfg(aktif=True), k)
    assert d["acik"] is False
    assert d["olculebilir"] is False
    assert "ÖLÇÜM İÇERMİYOR" in d["gerekce"]
    assert "ölçülmedi" in d["gerekce"]


def test_kapi_olculebilir_ama_olumsuz_karne_eski_gerekceyi_korur():
    """Gerçekten ölçülüp olumsuz çıkmışsa mesaj DEĞİŞMEMELİ."""
    k = {"cozulmus": 50, "gram_etkisi_pct": -1.0, "isabet_farki_puan": 20.0,
         "olculebilir_mi": True, "sat_hukum_sayisi": 12}
    d = karar.kapi_durumu(_cfg(aktif=True), k)
    assert d["acik"] is False and d["olculebilir"] is True
    assert d["gerekce"] == "karnede gram etkisi pozitif değil"


def test_karar_ver_olculemez_karneyi_raporda_bagirir():
    k = karar.karar_ver({"reel_net_mevduat": 5.0}, _cfg(aktif=False), _engel(),
                        karne={"cozulmus": 30, "isabet_pct": 64.0, "taban_pct": 64.0,
                               "isabet_farki_puan": 0.0, "gram_etkisi_pct": 0.0,
                               "olculebilir_mi": False, "sat_hukum_sayisi": 0,
                               "kol": "taktik", "yeterli_mi": True})
    md = karar.format_karar_md(k)
    assert "ÖLÇÜLEMİYOR" in md
    assert "fark +0.0p" not in md, "totoloji ölçüm gibi yazılmış"


# ---------------- kademenin kanıtı (2026-07-29) ----------------
#
# GERÇEK OLAY: sistemin ŞU AN AÇIK olan tek kolu (çekirdek) `reel_mevduat > %10`
# kuralıyla "AZ AL 0.75×" diyordu, ama aynı kural aday taramasında +1.34p ile
# kendi başa baş eşiğinin (+1.99p) ALTINDA kalıyordu. Rapor bunu hiçbir yerde
# söylemiyordu; okuyan "ölçtü ve geçti" sanıyordu. Bu testler o satırı kilitler.

def _tarama(fark=1.34, n=22, t=1.03, gecti=False, kural="reel_mevduat > %10"):
    return {"esik_cekirdek_puan": 1.99, "esik_taktik_puan": 3.18, "zayif_n": 30,
            "adaylar": {kural: {"fark_puan": fark, "n": n, "t": t,
                                "yeterli": n >= 30, "cekirdek_gecti": gecti,
                                "taktik_gecti": False}},
            "cekirdek_gecen": [kural] if gecti else []}


def test_kademe_kurali_tarama_adayiyla_eslesir():
    """SÖZLEŞME: kademeyi üreten kuralın adı, taramadaki aday adıyla BİREBİR
    aynı olmalı. Ayrışırsa rapor sessizce 'kural taramada YOK'a düşer ve
    kademenin kanıt durumu bir daha hiç ölçülemez."""
    from src import tahmin_backfill as tb
    dusuk = karar.cekirdek_hukum(-1.0, ESIK)["kural"]
    yuksek = karar.cekirdek_hukum(99.0, ESIK)["kural"]
    assert dusuk in tb.ADAYLAR, f"{dusuk!r} aday taramasında yok"
    assert yuksek in tb.ADAYLAR, f"{yuksek!r} aday taramasında yok"
    assert karar.cekirdek_hukum(5.0, ESIK)["kural"] is None      # ara bant


def test_kademe_esigin_altindaysa_raporda_ALTINDA_yazar():
    c = karar.cekirdek_hukum(13.0, ESIK)          # AZ AL 0.75×
    s = "\n".join(karar.kademe_kaniti_satiri(c, _tarama()))
    assert "ALTINDA" in s
    assert "+1.34p" in s and "1.99" in s          # sayılar gizlenmiyor
    assert "N=22" in s


def test_kademe_yokken_kanit_satiri_yazilmaz():
    """Ara bantta alım ertelenmiyor → ölçülecek iddia da yok."""
    c = karar.cekirdek_hukum(5.0, ESIK)
    assert c["carpan"] == 1.0
    assert karar.kademe_kaniti_satiri(c, _tarama()) == []


def test_kademe_kural_taramada_yoksa_sessiz_kalmaz():
    """Config eşiği taramadan ayrışırsa satır SUSMAZ — ölçülmemiş bir kademe
    ölçülmüş görünmemeli."""
    c = karar.cekirdek_hukum(13.0, ESIK)
    s = "\n".join(karar.kademe_kaniti_satiri(c, _tarama(kural="baska_kural")))
    assert "YOK" in s and "ölçülmemiş" in s


def test_kademe_esigi_gecse_bile_zayifsa_kanit_denmez():
    c = karar.cekirdek_hukum(13.0, ESIK)
    s = "\n".join(karar.kademe_kaniti_satiri(c, _tarama(fark=2.9, n=6, t=1.0,
                                                        gecti=True)))
    assert "aday, kanıt değil" in s


def test_kademe_kaniti_tarama_yoksa_cokmez():
    """Niyet: `tarama=None` gelince rapor üretimi PATLAMAMALI.

    2026-08-11'e kadar burada `== []` yazıyordu; bu, çökme güvenliğini değil
    SESSİZLİĞİ kilitliyordu ve gerçek bir arızayı görünmez kıldı: önbellek
    dosyası repoya hiç commit'lenmediği için satır 7/7 üretim raporunda
    basılmadı. Kodun komşu dalı ("kural taramada YOK") zaten "sessiz kalmak
    yerine söyle" diyordu — bu dal onunla tutarsızdı. İddia düzeltildi,
    niyet korundu; sessizliği bekleyen davranış artık
    `test_kademe_kaniti_onbellek_yokken_SESSIZ_KALMAZ` ile kilitli.
    """
    c = karar.cekirdek_hukum(13.0, ESIK)
    satir = karar.kademe_kaniti_satiri(c, None)   # istisna fırlatmamalı
    assert isinstance(satir, list)


def test_kademe_kaniti_onbellek_yokken_SESSIZ_KALMAZ():
    """2026-08-11 denetimi: `data/aday_taramasi.json` repoya hiç commit'lenmemişti;
    `tarama=None` gelince satır sessizce düşüyordu ve satır 7/7 üretim raporunda
    HİÇ basılmadı — STATE.md ise "her gün beyan ediyor" diyordu (L-008/L-011)."""
    cekirdek = {"carpan": 0.75, "kural": "reel_mevduat > %10"}
    satir = karar.kademe_kaniti_satiri(cekirdek, None)
    assert satir, "önbellek yokken satır sessizce düşmemeli"
    metin = "\n".join(satir)
    assert "aday_taramasi.json" in metin, "hangi dosyanın eksik olduğu yazılmalı"
    assert "YOK" in metin


def test_kademe_yokken_satir_hala_yazilmiyor():
    """Kademe 1.0× ise ertelenen alım yok → ölçülecek iddia da yok."""
    assert karar.kademe_kaniti_satiri({"carpan": 1.0, "kural": "x"}, None) == []
    assert karar.kademe_kaniti_satiri({"carpan": 1.0, "kural": "x"}, {"esik_cekirdek_puan": 2.0}) == []
