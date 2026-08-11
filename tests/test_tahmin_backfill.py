"""Aday taraması testleri.

Bu modülün en büyük riski **yanlış pozitif**: taramanın bir adayı hatalı olarak
"eşiği geçti" işaretlemesi. Öyle bir hata doğrudan SAT kapısının açılmasına
gerekçe olurdu. Testler bu yüzden ağırlıklı olarak eşik/örtüşme/uyarı
mantığını kilitler, tarama hızını değil.
"""
import copy

import pytest

from src import db, tahmin_backfill as tb, util

CFG = util.load_config()


def _cfg(tmp_path):
    c = copy.deepcopy(CFG)
    c["paths"]["db"] = str(tmp_path / "t.sqlite")
    c["paths"]["db_dump"] = str(tmp_path / "t.sql")
    return c


# ---------- aday kuralları ----------
def test_aday_kurali_none_veriyi_tetiklemez():
    """Özellik yoksa aday TETİKLENMEZ — eksik veri 'koşul sağlandı' sayılamaz."""
    for ad, kural in tb.ADAYLAR.items():
        assert kural({}) is None, ad


def test_aday_kurali_esik_yonu_dogru():
    ust = tb.ADAYLAR["reel_mevduat > %10"]
    assert ust({"reel_net_mevduat": 12.0}) is True
    assert ust({"reel_net_mevduat": 8.0}) is False
    alt = tb.ADAYLAR["reel_mevduat < 0"]
    assert alt({"reel_net_mevduat": -1.0}) is True
    assert alt({"reel_net_mevduat": 1.0}) is False


def test_aday_listesi_bos_degil():
    assert len(tb.ADAYLAR) >= 10


# ---------- t istatistiği ----------
def test_t_istatistigi_tabandan_uzaklastikca_buyur():
    orn = [1.0, 1.1, 0.9, 1.05, 0.95] * 4
    yakin = tb.t_istatistigi(orn, 1.0)
    uzak = tb.t_istatistigi(orn, 0.0)
    assert abs(uzak) > abs(yakin)


def test_t_istatistigi_kucuk_ornek_none():
    assert tb.t_istatistigi([1.0, 2.0], 0.0) is None


def test_t_istatistigi_sifir_varyans_none():
    assert tb.t_istatistigi([1.0] * 10, 0.0) is None


# ---------- eşik mantığı: yanlış pozitif koruması ----------
def _tarama(fark, n=50, t=3.0, gecti=None, taban=-1.99, rt=1.20):
    esik = abs(taban) + rt
    esik_cek = abs(taban)                  # çekirdek makas ÖDEMEZ
    return {"ufuk": "1ay", "ufuk_gun": 21, "n_asof": 400, "n_test": 14,
            "roundtrip_pct": rt, "zayif_n": 30, "esik_puan": esik,
            "esik_cekirdek_puan": esik_cek,
            "ilk": "2017-01-19", "son": "2026-07-24",
            "taban": {"ortalama": taban, "n_bagimsiz": 121},
            "adaylar": [{"aday": "test", "n": n, "ortalama": taban + fark,
                         "fark_puan": fark, "t": t, "kazanma_pct": 50.0,
                         "esigi_gecti": (fark > esik) if gecti is None else gecti,
                         "cekirdek_gecti": fark > esik_cek,
                         "yeterli": n >= 30}]}


def test_fixture_ureticinin_semasindan_sapmiyor(tmp_path):
    """SÖZLEŞME: elle yazılmış `_tarama` fixture'ı `tara`'nın gerçek çıktısıyla
    aynı anahtarlara sahip olmalı.

    Gerçek olay: `esik_cekirdek_puan` eklenince fixture eskidi ve 8 test
    KeyError ile düştü. Sessizce düşmeyip biçimlendiriciyi patlatması iyi
    haberdi — ama fixture'ın yeni bir alanı ATLAMASI (ör. bir bayrağı hiç
    kurmaması) sessiz kalırdı. Bu test o sessizliği kapatır.
    """
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con, n=400)
    gercek = tb.tara(c, con, adim_gun=40)
    con.close()
    sahte = _tarama(fark=0.0)
    assert set(sahte) == set(gercek), \
        f"fixture sapması: eksik={set(gercek) - set(sahte)}, " \
        f"fazla={set(sahte) - set(gercek)}"
    gercek_aday = next(a for a in gercek["adaylar"] if a.get("n"))
    assert set(sahte["adaylar"][0]) == set(gercek_aday), \
        f"aday sapması: eksik={set(gercek_aday) - set(sahte['adaylar'][0])}"


def test_esigi_gecmeyen_aday_gecti_isaretlenmez():
    """Taban -1.99, maliyet 1.20 → eşik 3.19. Fark 3.0 YETMEZ."""
    md = tb.format_tarama_md(CFG, _tarama(fark=3.0))
    assert "Hiçbir aday eşiği geçmedi" in md


def test_esigi_gecen_aday_yakalanir():
    md = tb.format_tarama_md(CFG, _tarama(fark=4.0, n=50, t=3.0))
    assert "eşiği geçti hem |t| ≥ 2" in md
    assert "canlıda denemeye değer" in md
    assert "'çalışıyor' demek DEĞİL" in md


def test_esigi_gecen_ama_zayif_n_guclu_sayilmaz():
    """N=6 ile +2.85p geçse bile 'güçlü aday' denemez."""
    md = tb.format_tarama_md(CFG, _tarama(fark=4.0, n=6, t=3.0))
    assert "hiçbiri güçlü değil" in md


def test_esigi_gecen_ama_zayif_t_guclu_sayilmaz():
    """|t| < 2 kanıt değildir — N büyük olsa bile."""
    md = tb.format_tarama_md(CFG, _tarama(fark=4.0, n=100, t=1.4))
    assert "hiçbiri güçlü değil" in md


def test_rapor_karne_olmadigini_bagirarak_soyler():
    md = tb.format_tarama_md(CFG, _tarama(fark=0.0))
    assert "BU BİR KARNE DEĞİLDİR" in md
    assert "örneklem-**İÇİ**" in md
    assert "kaynak='canli'" in md


def test_rapor_bonferroni_uyarisi_tasir():
    md = tb.format_tarama_md(CFG, _tarama(fark=0.0))
    assert "14 karşılaştırma yapıldı" in md


def test_rapor_zayif_n_bayragi():
    md = tb.format_tarama_md(CFG, _tarama(fark=0.0, n=6))
    assert "⚠️" in md and "ölçüm yetersiz" in md


def test_hic_tetiklenmeyen_aday_bos_gosterilir():
    t = _tarama(fark=0.0)
    t["adaylar"][0].update({"n": 0, "yeterli": False})
    assert "hiç tetiklenmedi" in tb.format_tarama_md(CFG, t)


# ---------- uçtan uca (sentetik) ----------
def _doldur(con, n=900):
    ons_sym = CFG["chart"]["ohlc"]["symbols"]["ons"]
    kur_sym = CFG["chart"]["ohlc"]["symbols"]["kur"]
    ev = CFG["sources"]["evds"]["series"]
    from datetime import date, timedelta
    d0 = date(2020, 1, 1)
    for i in range(n):
        d = (d0 + timedelta(days=i)).isoformat()
        ons, kur = 2000.0 * (1.0003 ** i), 30.0 * (1.0006 ** i)
        con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                    "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, ons, kur, ons * kur / 31.1035, "test"))
        for sym, p in ((ons_sym, ons), (kur_sym, kur)):
            con.execute("INSERT OR REPLACE INTO ohlc_daily(date,symbol,o,h,l,c,"
                        "v,source) VALUES(?,?,?,?,?,?,?,?)",
                        (d, sym, p, p * 1.01, p * 0.99, p, 0, "test"))
        if i % 30 == 0:
            for kod, val in ((ev["mevduat_3ay"], 45.0), (ev["mevduat_1yil"], 47.0),
                             (ev["aofm_politika"], 40.0), (ev["enf_bek_12ay"], 24.0)):
                con.execute("INSERT OR REPLACE INTO evds_daily(date,series_code,"
                            "value) VALUES(?,?,?)", (d, kod, val))
    con.commit()


def test_tara_ucdan_uca_calisir(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con)
    t = tb.tara(c, con, adim_gun=20)
    con.close()
    assert t["n_asof"] > 0
    assert t["esik_puan"] > 0
    assert len(t["adaylar"]) == len(tb.ADAYLAR)
    assert tb.format_tarama_md(c, t)


def test_tara_ortusmeyen_pencere_kullanir(tmp_path):
    """Bir aday sürekli tetiklense bile örnek sayısı, örtüşmeyen pencere
    sayısını AŞAMAZ. Aşarsa N şişer ve t değeri sahte güç kazanır."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con, n=900)
    t = tb.tara(c, con, adim_gun=5)
    con.close()
    h = t["ufuk_gun"]
    ust_sinir = 900 // h + 1
    for a in t["adaylar"]:
        assert a["n"] <= ust_sinir, f"{a['aday']}: N={a['n']} > {ust_sinir}"


# ---------- çekirdek eşiği (2026-07-29) ----------
#
# Tarama eskiden YALNIZ taktik eşiğini raporluyordu. Çekirdek kol AÇIK olduğu
# halde onun eşiğine göre hiçbir hüküm verilmiyordu; bir aday taktikte ❌ görünüp
# çekirdekte eşiği geçiyor olabilirdi ve ❌ okuyan yanlış sonuca varırdı.

def test_cekirdek_esigi_taktikten_dusuk():
    t = _tarama(fark=0.0)
    assert t["esik_cekirdek_puan"] < t["esik_puan"]


def test_taktikte_kalan_aday_cekirdekte_gecebilir():
    """+2.85p: taktik eşiği 3.19'un altında ama çekirdek eşiği 1.99'un üstünde.
    Rapor ikisini AYRI göstermeli."""
    md = tb.format_tarama_md(CFG, _tarama(fark=2.85, n=6, t=1.0))
    assert "Çekirdek kolun hükmü" in md
    assert "Taktik kolun hükmü" in md
    assert "| ❌ | ✅ |" in md, "aynı aday iki kolda aynı işareti almış"


def test_cekirdek_hukmu_eşik_altinda_kalirsa_yok_der():
    md = tb.format_tarama_md(CFG, _tarama(fark=1.0))
    assert "Hiçbir aday çekirdek eşiğini de geçmedi" in md


def test_cekirdek_esigi_gram_esik_pct_ile_ayni_kaynaktan(tmp_path):
    """TEK KAYNAK: eşik `gram.esik_pct` ile hesaplanmalı, elle değil."""
    from src import gram
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con, n=400)
    t = tb.tara(c, con, adim_gun=40)
    con.close()
    rt = gram.roundtrip_cost_pct(c, c["karar"]["enstruman"])
    assert t["esik_cekirdek_puan"] == pytest.approx(
        gram.esik_pct(t["taban"]["ortalama"], rt, "cekirdek"))
    assert t["esik_puan"] == pytest.approx(
        gram.esik_pct(t["taban"]["ortalama"], rt, "taktik"))


def test_tarama_ozeti_kararin_okudugu_alanlari_tasir(tmp_path):
    """`karar.kademe_kaniti_satiri` bu anahtarları okuyor; sözleşme kilitli."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con, n=400)
    o = tb.tarama_ozeti(tb.tara(c, con, adim_gun=40))
    con.close()
    assert {"esik_cekirdek_puan", "zayif_n", "adaylar"} <= set(o)
    assert isinstance(o["adaylar"], dict)
    for ad, a in o["adaylar"].items():
        assert {"fark_puan", "n", "t", "yeterli", "cekirdek_gecti"} <= set(a), ad


def _doldur_rejimli(con, n=900, donum=600):
    """İki rejimli sentetik seri: `reel_mevduat > %10` yalnız İKİNCİ yarıda
    tetiklenir ve orada gram DÜŞER (satmak kazandırır).

    Düz üstel seride her adayın farkı ÖZDEŞ 0 çıkıyor; öyle bir veriyle
    "cekirdek_gecti" bayrağı hiç True olmuyor ve onu sabit False yapan bir
    mutasyon testlerden SESSİZCE geçiyordu (2026-07-29 mutasyon koşumu M5).
    """
    ons_sym = CFG["chart"]["ohlc"]["symbols"]["ons"]
    kur_sym = CFG["chart"]["ohlc"]["symbols"]["kur"]
    ev = CFG["sources"]["evds"]["series"]
    from datetime import date, timedelta
    d0 = date(2018, 1, 1)
    for i in range(n):
        d = (d0 + timedelta(days=i)).isoformat()
        # 1. rejim: ons hızla artar (satmak kaybettirir)
        # 2. rejim: ons geriler (satmak kazandırır)
        ons = 2000.0 * (1.0010 ** i) if i < donum else \
            2000.0 * (1.0010 ** donum) * (0.9990 ** (i - donum))
        kur = 30.0 * (1.0002 ** i)
        con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                    "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, ons, kur, ons * kur / 31.1035, "test"))
        for sym, p in ((ons_sym, ons), (kur_sym, kur)):
            con.execute("INSERT OR REPLACE INTO ohlc_daily(date,symbol,o,h,l,c,"
                        "v,source) VALUES(?,?,?,?,?,?,?,?)",
                        (d, sym, p, p * 1.01, p * 0.99, p, 0, "test"))
        if i % 30 == 0:
            # enf_bek 35 → reel ≈ +3.7 (tetiklemez) · 24 → reel ≈ +12.9 (tetikler)
            bek = 35.0 if i < donum else 24.0
            for kod, val in ((ev["mevduat_3ay"], 45.0), (ev["mevduat_1yil"], 47.0),
                             (ev["aofm_politika"], 40.0), (ev["enf_bek_12ay"], bek)):
                con.execute("INSERT OR REPLACE INTO evds_daily(date,series_code,"
                            "value) VALUES(?,?,?)", (d, kod, val))
    con.commit()


def test_cekirdek_bayragi_gercekten_hesaplaniyor(tmp_path):
    """KİLİT TEST: `cekirdek_gecti` sabit False'a çevrilirse BU test düşer.

    Diğer eşik testleri elle yazılmış fixture üzerinden çalıştığı için
    üreticinin bayrağı hiç doğrulanmıyordu.
    """
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur_rejimli(con)
    t = tb.tara(c, con, adim_gun=10)
    con.close()

    tetikleyen = [a for a in t["adaylar"] if a.get("n")]
    assert tetikleyen, "hiçbir aday tetiklenmedi — veri kurgusu bozuk"
    esik = t["esik_cekirdek_puan"]
    gecmesi_gereken = [a for a in tetikleyen if a["fark_puan"] > esik]
    assert gecmesi_gereken, \
        f"kurgu eşiği aşan aday üretmedi (eşik {esik:.2f}p); test vacuous olurdu"
    for a in gecmesi_gereken:
        assert a["cekirdek_gecti"] is True, \
            f"{a['aday']}: fark {a['fark_puan']:+.2f}p > {esik:.2f}p ama bayrak False"
    for a in tetikleyen:
        assert a["cekirdek_gecti"] == (a["fark_puan"] > esik), a["aday"]


def test_taktigi_gecen_cekirdegi_de_gecer(tmp_path):
    """Taktik eşiği çekirdekten YÜKSEK → taktiği geçen çekirdeği de geçmeli.
    Tersi olursa iki eşikten biri yanlış hesaplanıyor demektir."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur_rejimli(con)
    t = tb.tara(c, con, adim_gun=10)
    con.close()
    for a in t["adaylar"]:
        if a.get("esigi_gecti"):
            assert a["cekirdek_gecti"], a["aday"]
