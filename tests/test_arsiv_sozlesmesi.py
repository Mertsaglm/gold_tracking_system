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
    # '$': Truncgil YALNIZ ons alanında para birimi işareti koyuyor. Bu düşmezse
    # ons sessizce None olur ve prim'in teorik bacağı boş kalır (ADR: ons spot'a
    # taşındı, 2026-08-15).
    assert util.parse_tr_number("$4.376,71") == pytest.approx(4376.71)
    for bos in (None, "", "-", "N/A", "null", "None", "abc"):
        assert util.parse_tr_number(bos) is None
    assert util.parse_tr_number(42) == 42.0
    assert util.parse_tr_number(4.5) == 4.5


def test_ons_truncgil_spottan_gelir_yfinance_vadeliden_degil(ornek_yanit, monkeypatch):
    """KİLİT TEST — 2026-07-29 arızasının tekrarını engeller.

    yfinance `GC=F` **sürekli seri değil, o anki vadeli kontrattır**. 2026-07-29'da
    Ağustos kontratı vadesini doldurdu, canlı kotasyon Aralık'a (GCZ26) atladı ve
    contango farkı (+%1.39) doğrudan `theoretical`'e girdi: prim 17 gün boyunca
    1.25 puan sahte iskonto gösterdi, `|prim| > %1.5` alarmı 4 gün üst üste
    (08-11…08-14) yanlış ateşledi ve Telegram'a gitti.

    Hiçbir test bunu yakalamadı çünkü hepsi DÖNGÜSELDİ: `gram_teorik == ons×kur/troy`
    aritmetiği doğrular, `ons`'un doğru enstrüman olduğunu DEĞİL.

    Bu test o boşluğu kapatır: `fetch_row` ons'u Truncgil spot'tan almalı ve
    yfinance ons'una — vadeli olduğu için — ASLA düşmemeli. Aksi hâlde arıza
    sessizce geri gelir.
    """
    sahte_vadeli = 9999.0                                   # kasten uçuk: düşerse görülür
    monkeypatch.setattr(yf, "fetch",
                        lambda cfg: yf.YfSnapshot(ons_usd=sahte_vadeli, usdtry=46.8431))
    row = archive_fetch.fetch_row(util.load_config())

    assert row["ons_usd"] != pytest.approx(sahte_vadeli), (
        "ons yfinance'ten (vadeli kontrat) alınmış — 2026-07-29 arızası geri geldi")
    assert row["ons_usd"] == pytest.approx(4149.01), "ons Truncgil spot 'Selling' olmalı"
    assert row["usdtry"] == pytest.approx(46.8431), "kur hâlâ yfinance'ten gelmeli"


def test_ons_yoksa_yfinance_yedegine_dusulmez(ornek_yanit, monkeypatch):
    """Sessiz yedek YASAK: yanlış bir ons, ons'suzluktan daha kötüdür.

    ons boşsa kayıt `indicative` olur ve prim hesaplanmaz — dürüst sonuç budur.
    Truncgil düşerse `gram_has` da düşer (ölçüldü 2026-07-29: geçersiz kayıtların
    20/20'sinde 8 alan BİRDEN boştu), yani kayıt zaten geçersizdir; ayrı bir ons
    yedeği hiçbir şey kurtarmaz, yalnız 1.25 puanlık hatayı geri getirir.
    """
    cfg = util.load_config()
    cfg["sources"]["truncgil"]["keys"] = {
        k: v for k, v in cfg["sources"]["truncgil"]["keys"].items() if k != "ons"}
    monkeypatch.setattr(yf, "fetch",
                        lambda c: yf.YfSnapshot(ons_usd=9999.0, usdtry=46.8431))
    row = archive_fetch.fetch_row(cfg)
    assert row["ons_usd"] is None, "ons yoksa None kalmalı, yfinance'e düşmemeli"


# ------------------------------------------------- kirli kaynak penceresi (ADR #013)
def test_kirli_pencere_saf_fonksiyon():
    """Sınırlar: başlangıç DAHİL, bitiş HARİÇ (yarı açık aralık)."""
    p = [{"ad": "x", "baslangic_utc": "2026-07-29T10:00:00+00:00",
          "bitis_utc": "2026-08-17T00:00:00+00:00"}]
    assert import_actions.kirli_pencere("2026-07-29T09:59:59+00:00", p) is None
    assert import_actions.kirli_pencere("2026-07-29T10:00:00+00:00", p) == "x"
    assert import_actions.kirli_pencere("2026-08-16T23:59:59+00:00", p) == "x"
    assert import_actions.kirli_pencere("2026-08-17T00:00:00+00:00", p) is None
    assert import_actions.kirli_pencere("2026-07-29T10:00:00+00:00", []) is None


def test_kirli_pencere_kaydi_z_tabanindan_duser(tmp_path, monkeypatch):
    """KİLİT TEST — kirli kayıt z-skor tabanına ve 60 günlük kapı sayacına GİRMEMELİ.

    Bu kural KOD'da durmak zorunda, DB'de değil: `insert_prim` INSERT OR REPLACE ve
    `import_all` her gün tüm arşivi baştan okuyor. Kayıtları elle işaretlemek bir
    sonraki Actions koşumunda sessizce silinirdi (ölçüldü 2026-08-16).

    Neden düşürüyoruz (ölçüldü, gerçek arşiv): kirli 14 gün bırakılsaydı z tabanı
    std=0.609 → tespit eşiği 1.22 puan; düşürülünce std=0.123 → eşik 0.25 puan.
    Yani kirlilik detektörü ~5 kat sağırlaştırıyordu ve genişleyen pencere olduğu
    için ASLA kendiliğinden düzelmiyordu.
    """
    from src import db, util as u
    kok = tmp_path
    (kok / "data" / "archive").mkdir(parents=True)
    (kok / "holidays_tr.yaml").write_text(
        (KOK / "holidays_tr.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    from src.archive_fetch import FIELDS
    def satir(ts, ons=4000.0, kur=47.0):
        teorik = ons / 31.1034768 * kur
        return ",".join([ts, f"{ons}", f"{kur}",
                         f"{teorik*1.006:.2f}", f"{teorik*1.0065:.2f}",
                         f"{teorik*1.004:.2f}", f"{teorik*1.0045:.2f}",
                         f"{teorik*1.804*0.916*1.02:.2f}",
                         f"{teorik*1.804*0.916*1.025:.2f}",
                         f"{kur-0.01}", f"{kur}"])
    TEMIZ = "2026-07-28T12:00:00+00:00"      # Salı, pencere ÖNCESİ
    KIRLI = "2026-07-30T12:00:00+00:00"      # Perşembe, pencere İÇİ
    with open(kok / "data" / "archive" / "2026-07.csv", "w",
              encoding="utf-8", newline="") as f:
        f.write(",".join(FIELDS) + "\n")
        f.write(satir(TEMIZ) + "\n")
        f.write(satir(KIRLI) + "\n")

    monkeypatch.setattr(u, "ROOT", kok)
    cfg = util.load_config()
    cfg["paths"]["db"] = str(kok / "t.sqlite")
    cfg["paths"]["holidays_file"] = str(kok / "holidays_tr.yaml")
    import_actions.import_all(cfg)

    con = db.connect(cfg)
    kayit = {r["ts_utc"]: r for r in con.execute(
        "SELECT ts_utc, indicative, reason, prim_pct FROM prim_history")}

    assert kayit[TEMIZ]["indicative"] == 0, "pencere dışı kayıt geçerli kalmalı"
    assert kayit[KIRLI]["indicative"] == 1, (
        "kirli pencere kaydı geçersiz işaretlenmedi — z tabanına sızıyor")
    assert kayit[KIRLI]["reason"].startswith("kirli_kaynak:"), \
        "sebep okunabilir olmalı, yoksa 6 ay sonra kimse neden bilmez"

    # asıl sözleşme: iki okuyucu da dışlamalı
    assert db.prim_series(con) == [pytest.approx(kayit[TEMIZ]["prim_pct"])], \
        "z tabanı yalnız temiz kaydı içermeli"
    assert db.count_valid_prim_days(con) == 1, "kapı sayacı kirli günü saymamalı"
    con.close()
