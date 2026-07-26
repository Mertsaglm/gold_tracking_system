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


def _engel(taban=-1.99, esik=3.19, beklenen=None):
    return {"ufuklar": {CFG["karar"]["birincil_ufuk"]: {
        "gun": 21, "n_bagimsiz": 121, "taban_ortalama_pct": taban,
        "kazanma_pct": 36.0, "en_kotu_pct": -36.2,
        "taktik_esik_puan": esik, "cekirdek_esik_puan": abs(taban),
        "beklenen_gram_kazanc_pct": beklenen,
    }}}


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
    k = {"cozulmus": 5, "gram_etkisi_pct": 3.0, "isabet_farki_puan": 20.0}
    assert karar.kapi_durumu(_cfg(aktif=True), k)["acik"] is False


def test_kapi_gram_etkisi_negatifse_kapali():
    """İsabet yüksek ama gram etkisi negatifse kapı AÇILMAZ — amaç fonksiyonu
    isabet değil, gram."""
    k = {"cozulmus": 50, "gram_etkisi_pct": -1.0, "isabet_farki_puan": 20.0}
    assert karar.kapi_durumu(_cfg(aktif=True), k)["acik"] is False


def test_kapi_tum_sartlar_saglanirsa_acik():
    k = {"cozulmus": 50, "gram_etkisi_pct": 2.0, "isabet_farki_puan": 15.0}
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
