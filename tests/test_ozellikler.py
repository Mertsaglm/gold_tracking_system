"""Özellik katmanı testleri — ağırlık merkezi LOOK-AHEAD.

`test_look_ahead_gelecek_silinince_ayni_sonuc` bu dosyanın varlık sebebidir:
`asof` sonrası TÜM satırlar silinmiş bir DB kopyasında `feature_vector` birebir
aynı sözlüğü döndürmeli. Döndürmüyorsa bir yerden gelecek sızıyordur ve
üretilecek her karne yalan olur.

Test gerçek `data/altin.sqlite`'ı DEĞİL, tmp_path'teki sentetik/kopya DB'yi
kullanır; hiçbir test ağa çıkmaz.
"""
import copy

import pytest

from src import db, ozellikler as oz, util

CFG = util.load_config()


def _cfg(tmp_path):
    c = copy.deepcopy(CFG)
    c["paths"]["db"] = str(tmp_path / "t.sqlite")
    c["paths"]["db_dump"] = str(tmp_path / "t.sql")
    return c


def _doldur(con, n=400):
    """Sentetik ama gerçekçi seri: gram yukarı sürükleniyor, kur sürünüyor."""
    ons_sym, kur_sym = CFG["chart"]["ohlc"]["symbols"]["ons"], \
        CFG["chart"]["ohlc"]["symbols"]["kur"]
    ev = CFG["sources"]["evds"]["series"]
    for i in range(n):
        d = f"{2024 + i // 365}-{1 + (i % 365) // 31:02d}-{1 + (i % 31):02d}"
        ons, kur = 2000.0 * (1.0004 ** i), 30.0 * (1.0008 ** i)
        con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                    "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, ons, kur, ons * kur / 31.1035, "test"))
        for sym, p in ((ons_sym, ons), (kur_sym, kur)):
            con.execute("INSERT OR REPLACE INTO ohlc_daily(date,symbol,o,h,l,c,v,"
                        "source) VALUES(?,?,?,?,?,?,?,?)",
                        (d, sym, p, p * 1.01, p * 0.99, p, 0, "test"))
        if i % 30 == 0:                       # aylık makro serileri
            for kod, val in ((ev["mevduat_3ay"], 45.0), (ev["mevduat_1yil"], 47.0),
                             (ev["aofm_politika"], 40.0), (ev["enf_bek_12ay"], 24.0)):
                con.execute("INSERT OR REPLACE INTO evds_daily(date,series_code,"
                            "value) VALUES(?,?,?)", (d, kod, val))
    con.commit()
    return con.execute("SELECT date FROM history_daily ORDER BY date").fetchall()


# ---------- saf çekirdek ----------
def test_getiri_pct():
    assert oz.getiri_pct([100.0, 110.0], 1) == pytest.approx(10.0)
    assert oz.getiri_pct([100.0], 5) is None


def test_donchian_konum_uc_noktalar():
    assert oz.donchian_konum([1.0, 2.0, 3.0], 3) == pytest.approx(1.0)   # tepede
    assert oz.donchian_konum([3.0, 2.0, 1.0], 3) == pytest.approx(0.0)   # dipte
    assert oz.donchian_konum([1.0, 3.0, 2.0], 3) == pytest.approx(0.5)   # ortada


def test_donchian_duz_seride_bolme_hatasi_yok():
    """Sabit seride hi==lo → 0.5 dönmeli, ZeroDivisionError değil."""
    assert oz.donchian_konum([5.0, 5.0, 5.0], 3) == 0.5


def test_yillik_oynaklik_duz_seride_sifir():
    assert oz.yillik_oynaklik_pct([100.0] * 70, 60) == pytest.approx(0.0)


def test_yillik_oynaklik_yetersiz_veri_none():
    assert oz.yillik_oynaklik_pct([100.0] * 10, 60) is None


def test_gunler_once():
    assert oz.gunler_once("2026-03-05", 35) == "2026-01-29"


def test_z_konum_sabit_seride_sifir():
    assert oz.z_konum(5.0, [5.0] * 30, 30) == 0.0


# ---------- EVDS yayın gecikmesi ----------
def test_evds_gecikme_yayinlanmamis_veriyi_gizler(tmp_path):
    """TÜFE ayın ~3'ünde önceki ay için yayınlanır. 2026-02-01 tarihli satır
    2026-02-10'da HENÜZ AÇIKLANMAMIŞTIR (35 gün gecikme) → görünmemeli."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    kod = CFG["sources"]["evds"]["series"]["tufe"]
    con.execute("INSERT INTO evds_daily(date,series_code,value) VALUES(?,?,?)",
                ("2026-02-01", kod, 100.0))
    con.commit()
    assert oz.evds_asof(con, kod, "2026-02-10", 35) is None      # henüz yok
    assert oz.evds_asof(con, kod, "2026-03-20", 35) == 100.0     # artık var
    con.close()


def test_evds_gecikme_sifirsa_donem_tarihi_gecerli(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    kod = CFG["sources"]["evds"]["series"]["aofm_politika"]
    con.execute("INSERT INTO evds_daily(date,series_code,value) VALUES(?,?,?)",
                ("2026-02-01", kod, 40.0))
    con.commit()
    assert oz.evds_asof(con, kod, "2026-02-02", 1) == 40.0
    con.close()


# ---------- LOOK-AHEAD: bu dosyanın varlık sebebi ----------
def test_look_ahead_gelecek_silinince_ayni_sonuc(tmp_path):
    """KİLİT TEST.

    `feature_vector(asof)` iki kez çağrılır: (a) tam DB'de, (b) asof sonrası
    HER SATIRI silinmiş DB'de. Sonuçlar birebir aynı olmalı. Fark varsa bir
    özellik geleceği okuyordur.
    """
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=400)]
    asof = tarihler[300]

    tam = oz.feature_vector(c, con, asof)

    for t in ("history_daily", "ohlc_daily", "evds_daily"):
        con.execute(f"DELETE FROM {t} WHERE date > ?", (asof,))
    con.commit()
    kirpik = oz.feature_vector(c, con, asof)
    con.close()

    assert tam.keys() == kirpik.keys()
    farklar = {k: (tam[k], kirpik[k]) for k in tam if tam[k] != kirpik[k]}
    assert not farklar, f"gelecek sızıyor: {farklar}"


def test_look_ahead_farkli_asof_farkli_sonuc(tmp_path):
    """Negatif kontrol: yukarıdaki test, fonksiyon hep sabit dönseydi de
    geçerdi. Farklı asof'ların GERÇEKTEN farklı sonuç verdiğini doğrula."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=400)]
    a = oz.feature_vector(c, con, tarihler[300])
    b = oz.feature_vector(c, con, tarihler[350])
    con.close()
    assert a["gram_teorik"] != b["gram_teorik"]
    assert a["asof_date"] != b["asof_date"]


def test_asof_sonrasi_satir_okunmuyor_sql_duzeyinde(tmp_path):
    """asof'tan sonraki fiyat UÇ DEĞER yapılırsa sonuç değişmemeli."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=400)]
    asof = tarihler[300]
    once = oz.feature_vector(c, con, asof)
    con.execute("UPDATE history_daily SET gram_teorik = gram_teorik * 100 "
                "WHERE date > ?", (asof,))
    con.commit()
    sonra = oz.feature_vector(c, con, asof)
    con.close()
    assert once == sonra


# ---------- içerik ----------
def test_feature_vector_beklenen_alanlari_uretir(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=400)]
    f = oz.feature_vector(c, con, tarihler[350])
    con.close()
    for alan in ("gram_teorik", "ons_usd", "usdtry", "gram_getiri_1ay",
                 "ons_gma200_uzaklik_pct", "kur_oynaklik_60g", "ons_donchian_20",
                 "ons_atr", "gram_rsi", "reel_net_mevduat", "kur_bacagi_payi"):
        assert alan in f, alan


def test_reel_net_mevduat_formulu(tmp_path):
    """net = brüt×(1−stopaj); reel = (1+net)/(1+beklenti) − 1.
    47 brüt, %15 stopaj, %24 beklenti → net 39.95 → reel ~12.9"""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _doldur(con, n=400)
    f = oz.feature_vector(c, con,
                          con.execute("SELECT MAX(date) d FROM history_daily"
                                      ).fetchone()["d"])
    con.close()
    assert f["reel_net_mevduat"] == pytest.approx(12.86, abs=0.1)


def test_gram_icin_ohlc_turetilmiyor(tmp_path):
    """db.py şema kuralı: gram TL için OHLC üretilmez → gram_atr OLMAMALI."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=400)]
    f = oz.feature_vector(c, con, tarihler[350])
    con.close()
    assert "gram_atr" not in f
    assert "gram_rsi" in f          # kapanış serisinden RSI meşru


def test_yasakli_kaynaklar_ozellige_girmiyor(tmp_path):
    """ADR #007: FRED / Trends / gld_tonnage / prim_history özelliklere GİRMEZ —
    canlıda hesaplanamayan ya da geleceği içeren kaynakların karnesi sahtedir."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=400)]
    f = oz.feature_vector(c, con, tarihler[350])
    con.close()
    yasakli = ("dfii", "dxy", "trends", "gld", "tonnage", "prim_z", "prim_pct")
    assert not [k for k in f if any(y in k.lower() for y in yasakli)]


def test_eksik_alanlar_veri_yetersizken_bildirir(tmp_path):
    """Kısa seride 12ay momentum ve GMA200 hesaplanamaz → eksik listelenmeli."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=50)]
    f = oz.feature_vector(c, con, tarihler[-1])
    con.close()
    eksik = oz.eksik_alanlar(f)
    assert "gram_getiri_12ay" in eksik and "ons_gma200" in eksik


def test_son_kapali_gun_bugunden_onceki(tmp_path):
    """asof = T−1: daily.yml 15:35 UTC'de koşarken o günün GC=F kapanışı yok."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=100)]
    assert oz.son_kapali_gun(con, bugun=tarihler[-1]) == tarihler[-2]
    con.close()


def test_son_kapali_gun_bugunu_VARSAYILAN_olarak_disar(tmp_path):
    """KİLİT TEST — `bugun` geçilmese bile bugünün YARIM barı asof olamaz.

    Bu fonksiyonun eski hâlinde filtre opsiyoneldi ve iki çağıranın da (
    `karar.build_karar`, `tahmin.kaydet`) hiçbiri onu geçmiyordu; garanti
    kâğıt üstündeydi. `history.update_recent` bugünün satırını yazdığı an
    (hafta içi her koşumda) asof bugüne kayardı.
    """
    c = _cfg(tmp_path)
    con = db.connect(c)
    tarihler = [r["date"] for r in _doldur(con, n=100)]
    bugun = util.local_today()
    # `update_recent`'ın hafta içi yaptığı şey: bugünün (yarım) barını yaz
    con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                (bugun, 4000.0, 47.0, 6045.0, "test-yarim-bar"))
    con.commit()
    assert con.execute("SELECT MAX(date) FROM history_daily").fetchone()[0] == bugun
    # ...ama asof ona ASLA kaymamalı
    asof = oz.son_kapali_gun(con)
    assert asof != bugun
    assert asof == tarihler[-1]
    con.close()


def test_tahmin_ve_karar_ayni_asof_yolunu_kullanir():
    """İkinci bir `MAX(date)` kopyası geri gelmesin (tek giriş noktası kuralı)."""
    import inspect

    from src import tahmin
    kaynak = inspect.getsource(tahmin)
    assert "_son_kapali_gun" not in kaynak, "tahmin.py'de ikinci asof yolu var"
    assert "oz.son_kapali_gun" in kaynak
