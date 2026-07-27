"""ARŞİV CSV'si ve KAYNAK ŞEMALARI — dış dünyayla temas yüzeyi.

`data/archive/YYYY-MM.csv` bu projenin ham hafızası: SQLite silinebilir (her gün
dump'tan kuruluyor) ama CSV arşivi ilk kesintisiz canlı veridir ve yalnız
BÜYÜR. İki kırılganlığı var:

1. **Alan sırası/adları.** `csv.DictWriter` aynı dosyaya ay boyunca ekleme
   yapıyor. Bir alan eklenir/çıkarılır ya da yeniden adlandırılırsa aynı dosyada
   iki farklı şema olur; `import_actions` alanları ADLA okuduğu için sessizce
   None üretir — geçersiz kayıt oranı yükselir ve sebebi görünmez.
2. **Truncgil JSON anahtarları.** Kaynak şemasını değiştirirse (bir kez
   `gram-has-altin` diye ayrı bir alan eklendi) config eşlemesi kayar. Bu
   repoda `tests/fixtures/truncgil_v3_sample.json` var ama HİÇBİR TEST onu
   kullanmıyordu — yani gerçek bir kaynak yanıtına karşı ayrıştırıcı hiç
   sınanmıyordu. Bu dosya o boşluğu kapatıyor.
"""
from __future__ import annotations

import csv
import json

import pytest

from src import archive_fetch, db, import_actions, util
from src.sources import truncgil, yf
from tests.conftest import KOK, arsiv_csv_yaz

ORNEK = KOK / "tests" / "fixtures" / "truncgil_v3_sample.json"


# ------------------------------------------------------------ CSV şeması
def test_alan_listesi_mevcut_arsiv_basligiyla_ayni():
    """KİLİT TEST. `FIELDS`, commit'li her CSV'nin başlığıyla BİREBİR eşleşmeli.

    Eşleşmezse: (a) yeni satırlar eski başlıkla yazılmaya devam eder ve alanlar
    kayar, (b) `DictWriter` fazla alanda `ValueError` fırlatır ve o turun verisi
    tamamen kaybolur.
    """
    dosyalar = sorted((KOK / "data" / "archive").glob("*.csv"))
    if not dosyalar:
        pytest.skip("arşiv CSV'si yok")
    for yol in dosyalar:
        with open(yol, encoding="utf-8") as f:
            baslik = next(csv.reader(f))
        assert baslik == archive_fetch.FIELDS, (
            f"{yol.name} başlığı FIELDS'ten farklı:\n  dosya: {baslik}\n"
            f"  kod  : {archive_fetch.FIELDS}")


def test_import_yalnizca_var_olan_alanlari_okuyor():
    """`import_actions`'ın okuduğu her alan adı `FIELDS`'te olmalı; olmayan bir
    ad daima None döner ve o metrik sessizce ölür (ADR #006-C kalıbı)."""
    kaynak = (KOK / "src" / "import_actions.py").read_text(encoding="utf-8")
    import re
    okunan = set(re.findall(r'row\.get\("([^"]+)"\)', kaynak))
    assert okunan, "tarama çalışmadı"
    eksik = okunan - set(archive_fetch.FIELDS)
    assert not eksik, f"CSV'de olmayan alanlar okunuyor: {sorted(eksik)}"


def test_append_row_basligi_bir_kez_yazar(izole_kok):
    """Ay dosyasına ekleme yapılıyor: başlık her satırda tekrarlanırsa
    `DictReader` onu veri satırı sanar ve `float()` çevrimi sessizce None üretir."""
    cfg, kok = izole_kok
    satir = {ad: "1" for ad in archive_fetch.FIELDS}
    satir["ts_utc"] = "2026-07-23T10:00:00+00:00"
    yol1 = archive_fetch.append_row(cfg, satir)
    satir2 = dict(satir, ts_utc="2026-07-23T10:15:00+00:00")
    yol2 = archive_fetch.append_row(cfg, satir2)
    assert yol1 == yol2, "aynı ay farklı dosyaya yazıldı"
    assert yol1.endswith("2026-07.csv"), "dosya adı ts_utc'nin ayından gelmeli"
    metin = util.abspath(yol1).read_text(encoding="utf-8")
    assert metin.count("ts_utc,ons_usd") == 1
    assert len(list(csv.DictReader(open(yol1, encoding="utf-8")))) == 2


def test_arsiv_dosyasi_aya_gore_bolunuyor(izole_kok):
    """Ay değişince yeni dosya: tek dev dosya diff'i her gün baştan yazardı."""
    cfg, _ = izole_kok
    temel = {ad: "1" for ad in archive_fetch.FIELDS}
    a = archive_fetch.append_row(cfg, dict(temel, ts_utc="2026-07-31T23:59:00+00:00"))
    b = archive_fetch.append_row(cfg, dict(temel, ts_utc="2026-08-01T00:01:00+00:00"))
    assert a.endswith("2026-07.csv") and b.endswith("2026-08.csv")


# ------------------------------------------------------------ import davranışı
def test_import_hafta_ici_kaydi_gecerli_sayar(izole_kok, sabit_zaman):
    """Hafta içi (forex açık) kayıt `indicative=0` → z-skor arşivine sayılır."""
    cfg, kok = izole_kok
    arsiv_csv_yaz(kok, satir_sayisi=4)
    sonuc = import_actions.import_all(cfg)
    assert sonuc["prim"] == 4
    con = db.connect(cfg)
    try:
        assert db.count_valid_prim(con) == 4
        assert con.execute("SELECT COUNT(*) FROM prim_history WHERE weekend=1"
                           ).fetchone()[0] == 0
    finally:
        con.close()


def test_import_hafta_sonu_kaydini_gecersiz_isaretler_ve_beklenti_yazar(izole_kok):
    """Forex kapalıyken prim HESAPLANIR ama `indicative=1` olur ve
    `weekend_expectation`'a yazılır — pazartesi mutabakatının girdisi budur."""
    cfg, kok = izole_kok
    yol = kok / "data" / "archive" / "2026-07.csv"
    with open(yol, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(archive_fetch.FIELDS) + "\n")
        # 2026-07-18 Cumartesi → forex kapalı
        f.write("2026-07-18T12:00:00+00:00,4000,47,6060,6065,6040,6045,"
                "10000,10100,46.99,47\n")
    sonuc = import_actions.import_all(cfg)
    assert sonuc["hafta_sonu"] == 1
    con = db.connect(cfg)
    try:
        r = con.execute("SELECT indicative, weekend FROM prim_history").fetchone()
        assert r["indicative"] == 1 and r["weekend"] == 1
        assert con.execute("SELECT COUNT(*) FROM weekend_expectation").fetchone()[0] == 1
        assert db.count_valid_prim(con) == 0, "hafta sonu z-skor tabanına girdi"
    finally:
        con.close()


def test_import_eksik_gram_satirini_prime_yazmaz(izole_kok):
    """Truncgil transient hatası (~%7): gram boş gelirse prim hesaplanamaz.
    Tick yazılır (ham veri kaybedilmez) ama prim satırı YAZILMAZ — yoksa
    yarım kayıt z-skor tabanını bozar."""
    cfg, kok = izole_kok
    yol = kok / "data" / "archive" / "2026-07.csv"
    with open(yol, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(archive_fetch.FIELDS) + "\n")
        f.write("2026-07-23T12:00:00+00:00,4000,47,,,,,,,46.99,47\n")
    sonuc = import_actions.import_all(cfg)
    assert sonuc["prim"] == 0
    assert sonuc["tick"] >= 2, "ons/kur tick'i de yazılmamış"


def test_import_prim_tablosunu_cift_yazmaz(izole_kok, sabit_zaman):
    """`prim_history` PRIMARY KEY(ts_utc) sayesinde idempotent: `daily_job` her
    gün tüm arşivi yeniden okuduğu için bu ŞART."""
    cfg, kok = izole_kok
    arsiv_csv_yaz(kok, satir_sayisi=5)
    import_actions.import_all(cfg)
    con = db.connect(cfg)
    ilk = con.execute("SELECT COUNT(*) FROM prim_history").fetchone()[0]
    con.close()
    import_actions.import_all(cfg)
    con = db.connect(cfg)
    try:
        assert con.execute("SELECT COUNT(*) FROM prim_history").fetchone()[0] == ilk
        assert con.execute("SELECT COUNT(*) FROM ohlc_1m").fetchone()[0] > 0
    finally:
        con.close()


def test_import_tick_tablosunu_da_cift_yazmaz(izole_kok, sabit_zaman):
    """KİLİT TEST (2026-07-27 onarımı).

    `daily_job` her koşumda TÜM arşivi baştan okuyor — dosya bazlı artımlılık
    yok. Eski `insert_tick` düz INSERT olduğu için aynı gözlem her gün yeniden
    yazılıyordu (kontrollü ölçüm: 5 satırlık CSV iki kez import → ticks 26→52;
    üretimde 9.6× şişme). Artık `ticks` benzersiz indeksli ve `INSERT OR IGNORE`.
    """
    cfg, kok = izole_kok
    arsiv_csv_yaz(kok, satir_sayisi=5)
    ilk_sonuc = import_actions.import_all(cfg)
    con = db.connect(cfg)
    ilk = con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    ilk_n = con.execute("SELECT SUM(n) FROM ohlc_1m").fetchone()[0]
    con.close()
    assert ilk_sonuc["tick"] == ilk

    ikinci_sonuc = import_actions.import_all(cfg)
    con = db.connect(cfg)
    try:
        assert con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == ilk
        assert ikinci_sonuc["tick"] == 0, "sayaç yazılmayan satırları da sayıyor"
        # `ohlc_1m.n` örnek sayacı da şişmemeli: yeniden okuma veri üretmez
        assert con.execute("SELECT SUM(n) FROM ohlc_1m").fetchone()[0] == ilk_n
    finally:
        con.close()


def test_import_yeni_satir_geldiginde_yazmaya_devam_ediyor(izole_kok, sabit_zaman):
    """Karşı kontrol: tekillik "hiç yazma"ya dönüşmemeli. Aynı dosyaya yeni
    satır eklendiğinde yalnız o satır işlenmeli."""
    cfg, kok = izole_kok
    arsiv_csv_yaz(kok, satir_sayisi=3)
    import_actions.import_all(cfg)
    con = db.connect(cfg)
    ilk = con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    con.close()

    arsiv_csv_yaz(kok, satir_sayisi=5)          # aynı dosya, 2 satır daha
    sonuc = import_actions.import_all(cfg)
    con = db.connect(cfg)
    try:
        assert con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] > ilk
        assert sonuc["tick"] > 0
        assert sonuc["gecerli_prim_toplam"] == 5
    finally:
        con.close()


# ------------------------------------------------------------ Truncgil şeması
@pytest.fixture
def ornek_yanit(monkeypatch):
    """Gerçek bir Truncgil v3 yanıtı (2026-07-07 örneği) ile ayrıştırıcıyı sınar."""
    veri = json.loads(ORNEK.read_text(encoding="utf-8"))

    class _Yanit:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return veri

    monkeypatch.setattr(truncgil.requests, "get", lambda *a, **k: _Yanit())
    return veri


def test_truncgil_configteki_tum_anahtarlari_cozuyor(ornek_yanit):
    """KİLİT TEST. config'teki her mantıksal ad gerçek yanıtta bulunmalı.

    Kaynak bir alanı yeniden adlandırırsa `truncgil.fetch` o sembolü sessizce
    ATLAR (`ok` yine True olabilir) ve prim hesaplanamaz. Bu test şema kaymasını
    kaynak yanıtına karşı yakalar.
    """
    cfg = util.load_config()
    snap = truncgil.fetch(cfg)
    assert snap.ok is True
    for mantiksal in cfg["sources"]["truncgil"]["keys"]:
        b, s = snap.bs(mantiksal)
        assert b is not None and s is not None, f"{mantiksal} çözülemedi"
        assert s > 0


def test_truncgil_tr_sayi_bicimini_dogru_okuyor(ornek_yanit):
    """'6.247,17' → 6247.17. Nokta binlik, virgül ondalık; yanlış yorum fiyatı
    1000 kat kaydırır ve prim %99 000 çıkar."""
    cfg = util.load_config()
    snap = truncgil.fetch(cfg)
    b, s = snap.bs("gram_altin")
    assert b == pytest.approx(6247.17) and s == pytest.approx(6248.14)
    hb, hs = snap.bs("gram_has_altin")
    assert hs == pytest.approx(6216.90)
    assert hs < s, "has gram perakende gramdan pahalı çıkmamalı"
    ub, us = snap.bs("usd")
    assert ub == pytest.approx(46.8366)
    assert snap.update_date == "2026-07-07 18:15:02"


def test_truncgil_prim_ornek_yanitta_makul(ornek_yanit):
    """Uçtan uca duman testi: örnek yanıttan hesaplanan prim ±%3 bandında olmalı
    (ons alanı $ işaretli ve binlik ayraçlı — ayrıştırma hatası burada patlar)."""
    from src import calc
    cfg = util.load_config()
    snap = truncgil.fetch(cfg)
    _, gram_has = snap.bs("gram_has_altin")
    _, usd = snap.bs("usd")
    ons = util.parse_tr_number(
        json.loads(ORNEK.read_text(encoding="utf-8"))["ons"]["Selling"].replace("$", ""))
    teorik = calc.theoretical_gram(ons, usd, cfg["instruments"]["troy_ounce_gram"])
    prim = calc.prim_pct(gram_has, teorik)
    assert abs(prim) < cfg["stats"]["prim_sane_band_pct"], f"prim %{prim:.2f}"


def test_truncgil_eksik_anahtari_atlar_cokmez(monkeypatch):
    """Şema toleransı: bir alan kaybolursa o sembol atlanır, süreç devam eder."""
    class _Yanit:
        def raise_for_status(self):
            pass

        def json(self):
            return {"USD": {"Buying": "46,80", "Selling": "46,85"},
                    "Update_Date": "2026-07-23 10:00:00"}

    monkeypatch.setattr(truncgil.requests, "get", lambda *a, **k: _Yanit())
    snap = truncgil.fetch(util.load_config())
    assert snap.ok is True                      # USD çözüldü
    assert snap.bs("gram_has_altin") == (None, None)


def test_truncgil_ag_hatasinda_ok_false(monkeypatch):
    """Ağ hatası çökme değil `ok=False` üretir; `archive_fetch` o turda boş
    yazar ve retry devreye girer (ADR #003)."""
    def _patla(*a, **k):
        raise OSError("ağ yok")

    monkeypatch.setattr(truncgil.requests, "get", _patla)
    snap = truncgil.fetch(util.load_config())
    assert snap.ok is False and snap.error
    assert snap.bs("usd") == (None, None)


def test_yf_hata_verse_de_snapshot_doner(monkeypatch):
    """yfinance düşerse ons/kur None döner; satır yine yazılır (ham veri
    kaybetmemek için) ve prim hesaplanmaz."""
    monkeypatch.setattr(yf, "_last_price", lambda *a, **k: None)
    snap = yf.fetch(util.load_config())
    assert snap.ons_usd is None and snap.usdtry is None


def test_tr_sayi_ayristirma_ozellikleri():
    """`parse_tr_number` dış dünyadan gelen her sayının kapısı."""
    assert util.parse_tr_number("6.247,17") == pytest.approx(6247.17)
    assert util.parse_tr_number("46,8366") == pytest.approx(46.8366)
    assert util.parse_tr_number("%-0,34") == pytest.approx(-0.34)
    assert util.parse_tr_number("1.234.567,89") == pytest.approx(1234567.89)
    for bos in (None, "", "-", "N/A", "null", "None", "abc"):
        assert util.parse_tr_number(bos) is None
    assert util.parse_tr_number(42) == 42.0
    assert util.parse_tr_number(4.5) == 4.5
