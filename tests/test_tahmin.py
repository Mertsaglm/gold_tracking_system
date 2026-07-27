"""Tahmin kaydı / çözüm / karne testleri.

Bu modül projenin dürüstlük altyapısı, bu yüzden testler iki şeyi kilitler:

1. **Değiştirilemezlik.** Karneyi güzelleştirmek için geçmiş bir tahmini
   "düzeltmek" kaçınılmaz bir ayartıdır. Şema bunu ABORT ile engelliyor;
   `test_tahmin_degistirilemez` bu korumanın kaldırılmasını yakalar.
2. **Giriş/çıkış simetrisi.** Yalnız çıkışı ortalamak, yukarı sürüklenen bir
   seride sistematik TUT yanlılığı yaratır — karne kendiliğinden güzelleşir.
"""
import sqlite3

import pytest

from src import db, gram, tahmin, util

CFG = util.load_config()


def _cfg(tmp_path):
    import copy
    c = copy.deepcopy(CFG)
    c["paths"]["db"] = str(tmp_path / "t.sqlite")
    c["paths"]["db_dump"] = str(tmp_path / "t.sql")
    return c


def _seri(con, n=200, baslangic=1000.0, gunluk=0.0):
    """Sentetik history_daily + sabit mevduat faizi."""
    for i in range(n):
        d = f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}"
        con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                    "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, 2000.0, 40.0, baslangic * (1 + gunluk) ** i, "test"))
    kod = CFG["sources"]["evds"]["series"]["mevduat_3ay"]
    con.execute("INSERT OR REPLACE INTO evds_daily(date,series_code,value) "
                "VALUES(?,?,?)", ("2026-01-01", kod, 36.0))
    con.commit()


# ---------- saf çekirdek ----------
def test_pencere_ortalamasi_uc_gun():
    assert tahmin.pencere_ortalamasi([10.0, 20.0, 30.0, 40.0], 2) == pytest.approx(30.0)


def test_pencere_ortalamasi_sinirda_kirpar():
    assert tahmin.pencere_ortalamasi([10.0, 20.0, 30.0], 0) == pytest.approx(15.0)


def test_pencere_ortalamasi_bos():
    assert tahmin.pencere_ortalamasi([], 0) is None
    assert tahmin.pencere_ortalamasi([1.0], 5) is None


def test_hedef_indeks_islem_gunu_sayar():
    """Takvim günü DEĞİL işlem günü — tatiller karneyi kaydırmasın."""
    t = ["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    assert tahmin.hedef_indeks(t, "2026-01-02", 2) == 3


def test_hedef_indeks_ufuk_tasarsa_none():
    t = ["2026-01-01", "2026-01-02"]
    assert tahmin.hedef_indeks(t, "2026-01-01", 21) is None


def test_tahmini_hedef_tarih_hafta_sonunu_hesaba_katar():
    """21 işlem günü ≈ 29 takvim günü."""
    assert tahmin.tahmini_hedef_tarih("2026-01-01", 21) == "2026-01-30"


def test_gram_etkisi_tut_sifir():
    """Satmadıysan gram sayın değişmez — hüküm ne kadar 'haklı' olursa olsun."""
    assert tahmin.gram_etkisi("TUT", 5.0, 1.2) == 0.0
    assert tahmin.gram_etkisi("AL_COK", -3.0, 1.2) == 0.0


def test_gram_etkisi_kismi_sat_oranli():
    """SAT_25 → kazancın da maliyetin de %25'i gerçekleşir."""
    assert tahmin.gram_etkisi("SAT_25", 5.0, 1.0) == pytest.approx(1.0)
    assert tahmin.gram_etkisi("SAT_50", 5.0, 1.0) == pytest.approx(2.0)


def test_gram_etkisi_maliyeti_asmayan_sat_negatif():
    """Haklı ama masrafını çıkarmayan SAT gram KAYBETTİRİR — karne bunu görmeli."""
    assert tahmin.gram_etkisi("SAT_50", 0.5, 1.2) < 0


def test_karne_ozeti_tabana_fark_hesaplar():
    s = [{"hukum": "TUT", "hukum_dogru": 1, "taban_dogru": 1, "gram_etkisi_pct": 0.0},
         {"hukum": "SAT_25", "hukum_dogru": 1, "taban_dogru": 0, "gram_etkisi_pct": 1.0},
         {"hukum": "TUT", "hukum_dogru": 0, "taban_dogru": 0, "gram_etkisi_pct": 0.0},
         {"hukum": "TUT", "hukum_dogru": 1, "taban_dogru": 1, "gram_etkisi_pct": 0.0}]
    k = tahmin.karne_ozeti(s, zayif_n=30)
    assert k["isabet_pct"] == pytest.approx(75.0)
    assert k["taban_pct"] == pytest.approx(50.0)
    assert k["isabet_farki_puan"] == pytest.approx(25.0)
    assert k["gram_etkisi_pct"] == pytest.approx(1.0)
    assert k["yeterli_mi"] is False          # N=4 < 30


def test_karne_bos():
    assert tahmin.karne_ozeti([], 30)["cozulmus"] == 0


# ---------- değiştirilemezlik ----------
def test_tahmin_degistirilemez(tmp_path):
    """KİLİT TEST: yazılmış bir hüküm sonradan düzeltilemez."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    with pytest.raises(sqlite3.IntegrityError, match="degistirilemez"):
        con.execute("UPDATE predictions SET hukum='SAT_50' WHERE id=1")
    con.close()


def test_sonuc_yazilabilir_ama_hukum_degil(tmp_path):
    """Sonuç tablosu ayrı: çözüm yazılabilmeli, hüküm asla."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    con.execute("UPDATE predictions SET created_utc='x' WHERE id=1")   # korumasız kolon
    con.commit()
    con.close()


# ---------- kayıt akışı ----------
def test_kaydet_her_ufuk_ve_kol_icin_satir_yazar(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con)
    ids = tahmin.kaydet(c, con, asof_date="2026-01-10")
    beklenen = len(c["karar"]["ufuklar_gun"]) * 2      # ufuk × (çekirdek+taktik)
    assert len(ids) == beklenen
    r = con.execute("SELECT COUNT(*) n FROM predictions").fetchone()
    assert r["n"] == beklenen
    con.close()


def test_kaydet_ikinci_cagri_cift_yazmaz(tmp_path):
    """daily_job aynı gün iki kez koşabilir — UNIQUE kısıtı buna dayanıklı."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    ikinci = tahmin.kaydet(c, con, asof_date="2026-01-10")
    assert ikinci == []
    con.close()


def test_kaydet_giris_fiyati_yazmaz(tmp_path):
    """Hüküm anında giriş fiyatı HENÜZ BİLİNMEZ — ayrı tabloda, ayrı adımda."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    assert con.execute("SELECT COUNT(*) n FROM prediction_entries").fetchone()["n"] == 0
    con.close()


def test_kapi_kapaliyken_kayitli_hukum_hep_tut(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    for r in con.execute("SELECT hukum, kapi_acik FROM predictions "
                         "WHERE kol='taktik'").fetchall():
        assert r["hukum"] == "TUT" and r["kapi_acik"] == 0
    con.close()


# ---------- giriş + çözüm ----------
def test_giris_doldur_sonra_cozum(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=200)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    assert tahmin.girisleri_doldur(c, con) > 0
    assert tahmin.cozumle(c, con) > 0
    o = con.execute("SELECT * FROM prediction_outcomes LIMIT 1").fetchone()
    assert o["gram_carry_kazanc_pct"] is not None
    assert o["roundtrip_maliyet_pct"] > 0
    con.close()


def test_cozum_yatay_fiyatta_sat_kazanir(tmp_path):
    """Fiyat sabit + mevduat faizi → SAT doğru, TUT yanlış. Ölü bant fiyat
    uzayında olsaydı bu ay 'yatay' sayılıp TUT lehine gidecekti."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=200, gunluk=0.0)          # tam yatay
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    tahmin.girisleri_doldur(c, con)
    tahmin.cozumle(c, con)
    r = con.execute("SELECT o.gram_carry_kazanc_pct, o.hukum_dogru "
                    "FROM prediction_outcomes o JOIN predictions p "
                    "ON p.id=o.prediction_id WHERE p.horizon_days=63 "
                    "AND p.kol='taktik'").fetchone()
    assert r["gram_carry_kazanc_pct"] > 0        # carry pozitif
    assert r["hukum_dogru"] == 0                 # TUT dedik ama SAT kazandı
    con.close()


def test_cozum_yukselen_fiyatta_tut_dogru(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=200, gunluk=0.003)        # günde binde 3 → aylık ~%6
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    tahmin.girisleri_doldur(c, con)
    tahmin.cozumle(c, con)
    r = con.execute("SELECT o.hukum_dogru FROM prediction_outcomes o "
                    "JOIN predictions p ON p.id=o.prediction_id "
                    "WHERE p.kol='taktik' LIMIT 1").fetchone()
    assert r["hukum_dogru"] == 1
    con.close()


def test_cozum_giris_ve_cikis_simetrik_ortalama(tmp_path):
    """Giriş de çıkış da 3 günlük ortalama. Asimetri, yukarı sürüklenen seride
    sistematik TUT yanlılığı yaratırdı."""
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=200, gunluk=0.003)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    tahmin.girisleri_doldur(c, con)
    e = con.execute("SELECT giris_date, giris_gram_teorik FROM prediction_entries "
                    "LIMIT 1").fetchone()
    tarihler, fiyatlar = tahmin._fiyat_serisi(con)
    i = tarihler.index(e["giris_date"])
    assert e["giris_gram_teorik"] == pytest.approx(
        tahmin.pencere_ortalamasi(fiyatlar, i))
    assert e["giris_gram_teorik"] != pytest.approx(fiyatlar[i])   # tek gün DEĞİL
    con.close()


def test_cozum_vadesi_gelmemisi_cozmez(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=30)                       # 63 günlük ufuk için yetersiz
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    tahmin.girisleri_doldur(c, con)
    tahmin.cozumle(c, con)
    kalan = con.execute(
        "SELECT COUNT(*) n FROM predictions p LEFT JOIN prediction_outcomes o "
        "ON o.prediction_id=p.id WHERE o.prediction_id IS NULL "
        "AND p.horizon_days=63").fetchone()["n"]
    assert kalan > 0
    con.close()


# ---------- karne ----------
def test_karne_bos_durumda_bekleyeni_bildirir(tmp_path):
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=30)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    k = tahmin.karne(c, con)
    assert k["cozulmus"] == 0 and k["bekleyen"] > 0
    assert "çözülmüş tahmin yok" in tahmin.format_karne_md(k)
    con.close()


def test_karne_gercek_uretimde_OLCUM_ICERMEDIGINI_soyler(tmp_path):
    """Kapı kapalıyken taktik kol yalnız TUT üretir → karne ölçüm İÇEREMEZ.

    Bu test eskiden "gram etkisini gösterir" diye yazılmıştı ve `+0.00%` görüp
    yeşil geçiyordu; oysa o sıfır piyasadan değil, `hukum_dogru_mu`'nun
    tanımından geliyordu (SAT olmayan her hüküm tabanla aynı cevabı alır).
    Karne artık bunu rakam yerine SEBEP yazarak söylüyor (ADR #008).
    """
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=200)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    tahmin.girisleri_doldur(c, con)
    tahmin.cozumle(c, con)
    k = tahmin.karne(c, con)
    con.close()
    assert k["cozulmus"] > 0
    assert k["sat_hukum_sayisi"] == 0
    assert k["olculebilir_mi"] is False
    # Kimlik olduğu için sayılar 0; ama rapor onları ÖLÇÜM gibi yazmamalı
    assert k["isabet_farki_puan"] == 0.0 and k["gram_etkisi_pct"] == 0.0
    md = tahmin.format_karne_md(k)
    assert "ÖLÇÜM İÇERMİYOR" in md
    assert "+0.0 puan" not in md and "+0.00%" not in md


def test_karne_SAT_hukmu_varsa_gercek_sayilari_yazar():
    """Ölçülebilir karne eski davranışını AYNEN korumalı (regresyon)."""
    rows = [
        {"hukum": "SAT_25", "hukum_dogru": True, "taban_dogru": False,
         "gram_etkisi_pct": 1.20},
        {"hukum": "SAT_25", "hukum_dogru": False, "taban_dogru": True,
         "gram_etkisi_pct": -0.40},
        {"hukum": "TUT", "hukum_dogru": True, "taban_dogru": True,
         "gram_etkisi_pct": 0.0},
    ]
    k = tahmin.karne_ozeti(rows, zayif_n=30)
    k.update(kol="taktik", kaynak="canli", model_version="v1.0", bekleyen=4)
    assert k["olculebilir_mi"] is True and k["sat_hukum_sayisi"] == 2
    md = tahmin.format_karne_md(k)
    assert "ÖLÇÜM İÇERMİYOR" not in md
    assert "Ölçüm yetersiz" in md            # N=3 < 30 → eski uyarı korunuyor
    assert "+0.80%" in md                    # 1.20 − 0.40


def test_karne_bos_olculebilir_degil():
    k = tahmin.karne_ozeti([], zayif_n=30)
    assert k["olculebilir_mi"] is False and k["sat_hukum_sayisi"] == 0


# ---------- dump/restore döngüsü ----------
def test_tahminler_dump_restore_sonrasi_yasar(tmp_path):
    """Actions stateless: DB her koşuda dump'tan restore ediliyor. Tahminler
    dump'a girmezse karne her gün sessizce sıfırlanırdı."""
    from src import dbdump
    c = _cfg(tmp_path)
    con = db.connect(c)
    _seri(con, n=200)
    tahmin.kaydet(c, con, asof_date="2026-01-10")
    tahmin.girisleri_doldur(c, con)
    tahmin.cozumle(c, con)
    once = con.execute("SELECT COUNT(*) n FROM predictions").fetchone()["n"]
    once_o = con.execute("SELECT COUNT(*) n FROM prediction_outcomes").fetchone()["n"]
    con.close()

    dbdump.dump(c)
    (tmp_path / "t.sqlite").unlink()
    dbdump.restore(c)

    con = db.connect(c)
    assert con.execute("SELECT COUNT(*) n FROM predictions").fetchone()["n"] == once
    assert con.execute(
        "SELECT COUNT(*) n FROM prediction_outcomes").fetchone()["n"] == once_o
    # FK bağı korundu mu: her sonucun sahibi bir tahmin var mı
    kopuk = con.execute(
        "SELECT COUNT(*) n FROM prediction_outcomes o LEFT JOIN predictions p "
        "ON p.id=o.prediction_id WHERE p.id IS NULL").fetchone()["n"]
    assert kopuk == 0
    con.close()
