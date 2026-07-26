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
    return {"ufuk": "1ay", "ufuk_gun": 21, "n_asof": 400, "n_test": 14,
            "roundtrip_pct": rt, "zayif_n": 30, "esik_puan": esik,
            "ilk": "2017-01-19", "son": "2026-07-24",
            "taban": {"ortalama": taban, "n_bagimsiz": 121},
            "adaylar": [{"aday": "test", "n": n, "ortalama": taban + fark,
                         "fark_puan": fark, "t": t, "kazanma_pct": 50.0,
                         "esigi_gecti": (fark > esik) if gecti is None else gecti,
                         "yeterli": n >= 30}]}


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
