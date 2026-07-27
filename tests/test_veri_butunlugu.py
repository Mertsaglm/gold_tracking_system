"""ÜRETİM VERİSİNİN bütünlüğü — `data/altin.sql` dump'ı denetlenir.

Bu dosya koddan çok VERİYİ test eder ve sebebi L-009: `git pull` dump'ı tazeler
ama gitignore'daki `data/altin.sqlite`'ı tazelemez; sonra yerelde alınan bir dump
1.5 günlük üretim verisini sessizce geri sardı (`prim_history` 251→238,
`ticks` 14 511→13 109). Dersin üçüncü kuralı aynen şu: *"`data/altin.sql` bir
commit'te değişiyorsa satır sayıları AZALMAMALI."*

Buradaki taban değerler (`TABANLAR`) o kuralın otomatik hâli — bir **kilit
dişlisi**: veri yalnız büyür, o yüzden taban yalnız YÜKSELTİLİR, asla
düşürülmez. Düşürmek gerektiğini düşünüyorsan önce "veri neden azaldı?"
sorusunu cevapla (L-009'un teşhis adımı).

Ayrıca ölçülmüş veri kuralları kilitlenir: hafta sonu barı yok (ADR #008-G),
bugünün yarım barı yok (ADR #008-D), `gram_teorik` gerçekten `ons × kur / troy`.
Testler dump'ı GEÇİCİ bir DB'ye restore eder; gerçek `data/altin.sqlite`'a
DOKUNMAZ (L-009'un tam olarak yasakladığı şey).
"""
from __future__ import annotations

import pytest

from src import calc, db, dbdump, util
from tests.conftest import KOK

DUMP = KOK / "data" / "altin.sql"

# Ölçüldü 2026-07-27. Taban = o günkü değerin biraz altı; veri büyüdükçe
# yükseltilebilir, ASLA düşürülmez (L-009).
TABANLAR = {
    "history_daily": 2500,      # ölçülen 2561 (2016-01-04 → 2026-07-24)
    "evds_daily": 7500,         # ölçülen 7659
    "ohlc_daily": 5300,         # ölçülen 5401 (GC=F + TRY=X)
    "prim_history": 250,        # ölçülen 265 (canlı arşiv, 2026-07-07'den)
    "ohlc_1m": 1600,            # ölçülen 1663
    "weekend_expectation": 85,  # ölçülen 91
}

pytestmark = pytest.mark.skipif(not DUMP.exists(), reason="data/altin.sql yok")


@pytest.fixture(scope="module")
def uretim_db(tmp_path_factory):
    """Üretim dump'ını GEÇİCİ bir sqlite'a restore eder (gerçek DB'ye dokunmaz)."""
    tmp = tmp_path_factory.mktemp("uretim")
    cfg = util.load_config()
    cfg["paths"]["db"] = str(tmp / "uretim.sqlite")     # absolute → abspath dokunmaz
    cfg["paths"]["db_dump"] = str(DUMP)
    sonuc = dbdump.restore(cfg)
    assert sonuc["restored"] is True, "üretim dump'ı restore edilemedi"
    con = db.connect(cfg)
    yield cfg, con, sonuc["counts"]
    con.close()


# ------------------------------------------------------------ dump sağlamlığı
def test_dump_restore_edilebiliyor(uretim_db):
    """KİLİT TEST. Bozuk bir dump = Actions'ın ilk adımının çökmesi = tüm
    geçmişin kaybı. Dump her koşumda restore ediliyor, yani okunabilirliği
    üretimin ön şartı."""
    _, _, sayilar = uretim_db
    assert sayilar["history_daily"] > 0


@pytest.mark.parametrize("tablo,taban", sorted(TABANLAR.items()))
def test_satir_sayisi_tabanin_altina_dusmedi(uretim_db, tablo, taban):
    """L-009 kilit dişlisi: veri azalmaz. Azaldıysa dump eski bir sqlite'tan
    üretilmiştir (yerelde `python -m src.dbdump` çalıştırma!)."""
    _, _, sayilar = uretim_db
    assert sayilar[tablo] >= taban, (
        f"{tablo}: {sayilar[tablo]} < taban {taban} — veri geriye sarılmış "
        "olabilir (L-009). Önce sebebi bul, tabanı düşürme.")


def test_dump_deterministik_siralamayla_yazilmis(uretim_db):
    """Dump diff'lenebilir olmalı: her tablo TEK bir blok ve bloklar
    `dbdump._TABLES` sırasında. Sıra bozulur ya da blok bölünürse her koşum dev
    bir diff üretir ve "yalnız yeni satırlar" garantisi düşer (repo şişer) —
    binary DB'yi commit'lememe kararının (Faz 5) tüm gerekçesi buydu.

    Not: veri içermeyen tablo bloğu, dump'ı üreten sürüm o tabloyu henüz
    bilmiyorsa hiç bulunmayabilir. Bu yüzden test SIRAYI denetler, eksiksizliği
    yalnız veri içeren tablolar için ister (tahmin tabloları üretimde ilk kez
    2026-07-27 akşamı yazılıyor).
    """
    _, _, sayilar = uretim_db
    metin = DUMP.read_text(encoding="utf-8")
    assert metin.startswith("-- Altin DB dump")
    beklenen_sira = [t for t, _, _ in dbdump._TABLES]
    bulunan = [s.split()[1].rstrip(":") for s in metin.splitlines()
               if s.startswith("-- ") and s.rstrip().endswith("satır")]
    assert len(bulunan) == len(set(bulunan)), f"tablo bloğu bölünmüş: {bulunan}"
    assert bulunan == [t for t in beklenen_sira if t in bulunan], (
        f"blok sırası _TABLES'tan farklı: {bulunan}")
    for tablo, adet in sayilar.items():
        if adet:
            assert tablo in bulunan, f"{tablo} {adet} satır içeriyor ama bloğu yok"


def test_dumpta_sema_yok_yalnizca_veri():
    """Şema KODDAN gelir (`db.SCHEMA`). Dump'a CREATE TABLE girerse şema iki
    kaynaklı olur ve kod değişince restore eski şemayı geri getirir."""
    metin = DUMP.read_text(encoding="utf-8")
    assert "CREATE TABLE" not in metin.upper()
    assert "CREATE TRIGGER" not in metin.upper()


# ------------------------------------------------------------ fiyat tutarlılığı
def test_gram_teorik_gercekten_ons_kur_carpimi(uretim_db):
    """`gram_teorik` türetilmiş bir fiyat: `ons / troy × kur`. Sapma varsa ya
    troy sabiti ya kur kaynağı değişmiş demektir — prim ve TÜM karar zinciri
    bunun üzerine kurulu."""
    cfg, con, _ = uretim_db
    troy = cfg["instruments"]["troy_ounce_gram"]
    satirlar = con.execute(
        "SELECT date, ons_usd, usdtry, gram_teorik FROM history_daily").fetchall()
    assert len(satirlar) >= TABANLAR["history_daily"]
    for r in satirlar:
        assert r["ons_usd"] and r["usdtry"] and r["gram_teorik"], f"{r['date']}: eksik alan"
        beklenen = calc.theoretical_gram(r["ons_usd"], r["usdtry"], troy)
        assert r["gram_teorik"] == pytest.approx(beklenen, rel=1e-9), r["date"]


def test_prim_kayitlarinda_teorik_ve_prim_tutarli(uretim_db):
    """Prim = piyasa/teorik − 1. Kayıtlı prim bu ilişkiyi bozuyorsa z-skor
    tabanı yanlış bir seriden hesaplanıyor."""
    _, con, _ = uretim_db
    for r in con.execute("SELECT ts_utc, theoretical, market_has, prim_pct "
                         "FROM prim_history WHERE prim_pct IS NOT NULL").fetchall():
        assert r["prim_pct"] == pytest.approx(
            calc.prim_pct(r["market_has"], r["theoretical"]), abs=1e-9), r["ts_utc"]


def test_prim_makul_bandin_icinde(uretim_db):
    """|prim| %3'ün dışına çıkan kayıt veri/şema sorununa işaret eder
    (`stats.prim_sane_band_pct`). Rapor bunu uyarı olarak yazıyor; tarihsel
    veride hiç olmaması gerekir."""
    cfg, con, _ = uretim_db
    band = cfg["stats"]["prim_sane_band_pct"]
    sapan = [(r["ts_utc"], r["prim_pct"]) for r in con.execute(
        "SELECT ts_utc, prim_pct FROM prim_history WHERE prim_pct IS NOT NULL")
        if abs(r["prim_pct"]) > band]
    assert not sapan, f"prim ±%{band} bandının dışında: {sapan[:5]}"


# ------------------------------------------------------------ ADR #008 kuralları
def test_ohlc_tablosunda_hafta_sonu_bari_yok(uretim_db):
    """ADR #008-G: ölçüldü, 5401 tarihsel barın 0'ı hafta sonu. Üretimdeki iki
    hayalet TRY=X satırı (2026-07-25/26) temizlendi ve filtre bağlandı; yeniden
    görünürlerse `drop_weekend_bars` yazma yolundan kopmuş demektir."""
    _, con, _ = uretim_db
    hayalet = [tuple(r) for r in con.execute(
        "SELECT date, symbol FROM ohlc_daily "
        "WHERE CAST(strftime('%w', date) AS INTEGER) IN (0, 6)")]
    assert not hayalet, f"hafta sonu barı: {hayalet}"


def test_bugunun_yarim_bari_hicbir_tabloda_yok(uretim_db):
    """ADR #008-D: koruma KAYNAKTA. Bugünün (ve ileri tarihli) satırın varlığı,
    `history_daily`/`ohlc_daily` yazma yolundaki filtrenin düştüğünü gösterir —
    ve o satır `predictions`'a değiştirilemez şekilde girmiş olabilir."""
    _, con, _ = uretim_db
    bugun = util.local_today()
    for tablo in ("history_daily", "ohlc_daily"):
        n = con.execute(f"SELECT COUNT(*) FROM {tablo} WHERE date >= ?",
                        (bugun,)).fetchone()[0]
        assert n == 0, f"{tablo}: bugün/ileri tarihli {n} satır"


def test_hafta_sonu_prim_kayitlari_gecersiz_isaretli(uretim_db):
    """Hafta sonu kaydı z-skor tabanına GİRMEZ. `weekend=1` ama `indicative=0`
    olan bir satır, forex kapalıyken toplanmış veriyi istatistiğe sokar."""
    _, con, _ = uretim_db
    n = con.execute("SELECT COUNT(*) FROM prim_history "
                    "WHERE weekend=1 AND indicative=0").fetchone()[0]
    assert n == 0, f"{n} hafta sonu kaydı geçerli sayılmış"


def test_gecerli_prim_gun_sayisi_kapi_ile_tutarli(uretim_db):
    """Kapı GÜN sayıyor. Kayıt/gün oranı ~10 civarında olmalı (gün içi ~13
    örnek); oran 1'e yaklaşırsa gün bazlı sayım bozulmuş, 50'yi geçerse
    tekrarlı kayıt (bkz. ticks) sorunu prim tarafına da bulaşmış demektir."""
    _, con, _ = uretim_db
    gun = db.count_valid_prim_days(con)
    kayit = db.count_valid_prim(con)
    assert gun >= 15, f"geçerli gün sayısı beklenenden az: {gun}"
    assert 1 <= kayit / gun < 50, f"kayıt/gün oranı anormal: {kayit}/{gun}"


def test_evds_serilerinin_tamami_dumpta(uretim_db):
    """config'te tanımlı her EVDS serisi verisiyle dump'ta olmalı: eksik seri,
    `feature_vector`'ın o makro özelliğini sessizce None yapar."""
    cfg, con, _ = uretim_db
    mevcut = {r[0] for r in con.execute("SELECT DISTINCT series_code FROM evds_daily")}
    tanimli = set(cfg["sources"]["evds"]["series"].values())
    eksik = tanimli - mevcut
    assert not eksik, f"EVDS serisi dump'ta yok: {sorted(eksik)}"


def test_ohlc_sembolleri_configle_ayni(uretim_db):
    cfg, con, _ = uretim_db
    mevcut = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM ohlc_daily")}
    assert mevcut == set(cfg["chart"]["ohlc"]["symbols"].values()), (
        f"tabloda beklenmeyen sembol: {mevcut}")


def test_history_ve_ohlc_ayni_donemi_kapsiyor(uretim_db):
    """İkisi de 2016'dan başlıyor (config `backtest.start` / `chart.ohlc.start`).
    Biri geride kalırsa özellik vektörü kısa pencerede None üretir."""
    cfg, con, _ = uretim_db
    h_ilk, h_son = con.execute("SELECT MIN(date), MAX(date) FROM history_daily").fetchone()
    o_ilk = con.execute("SELECT MIN(date) FROM ohlc_daily").fetchone()[0]
    assert h_ilk <= cfg["backtest"]["start"][:4] + "-12-31"
    assert o_ilk <= cfg["chart"]["ohlc"]["start"][:4] + "-12-31"
    assert h_son >= "2026-07-01", f"history_daily {h_son}'de durmuş görünüyor"


# ------------------------------------------------------------ tahmin kayıtları
def test_kayitli_tahminler_tutarli(uretim_db):
    """Kayıt başladıktan sonra her satır kendi kurallarına uymalı.

    Henüz 0 satır olabilir (ilk yazım 2026-07-27 akşamı) — o zaman test
    boş kümeyi doğrular ve kayıt başladığı gün otomatik olarak anlam kazanır.
    """
    cfg, con, _ = uretim_db
    satirlar = con.execute(
        "SELECT asof_date, target_date, kol, hukum, kapi_acik, model_version, "
        "kaynak, horizon_days FROM predictions").fetchall()
    ufuklar = set(cfg["karar"]["ufuklar_gun"].values())
    for r in satirlar:
        assert r["asof_date"] < r["target_date"], "hedef asof'tan önce"
        assert r["kol"] in ("cekirdek", "taktik")
        assert r["kaynak"] in ("canli", "replay")
        assert r["kapi_acik"] in (0, 1)
        assert r["horizon_days"] in ufuklar
        assert r["asof_date"] < util.local_today(), "asof bugün ya da ileri tarihli"
        if r["kaynak"] == "canli":
            assert r["model_version"] == cfg["karar"]["model_version"], (
                "canlı karnede farklı model sürümü var — karne SIFIRLANMALIYDI")


def test_kapi_kapaliyken_kayitli_hicbir_hukum_SAT_degil(uretim_db):
    """`karar.taktik.aktif: false` iken üretimde SAT kaydı OLAMAZ. Varsa kapı
    bir ara açılmış (ya da kapı kontrolü atlanmış) demektir — karne için kritik."""
    _, con, _ = uretim_db
    satlar = [tuple(r) for r in con.execute(
        "SELECT asof_date, kol, hukum FROM predictions WHERE hukum LIKE 'SAT%' "
        "AND kapi_acik=0")]
    assert not satlar, f"kapı kapalıyken SAT kaydı: {satlar}"


def test_cozulmus_tahminlerin_girisi_de_var(uretim_db):
    """Çözüm zinciri: her sonucun bir girişi olmalı. Giriş olmadan çözülmüş bir
    tahmin, çıkışı olan ama girişi bilinmeyen bir ölçüm demektir."""
    _, con, _ = uretim_db
    kopuk = con.execute(
        "SELECT COUNT(*) FROM prediction_outcomes o "
        "LEFT JOIN prediction_entries e ON e.prediction_id = o.prediction_id "
        "WHERE e.prediction_id IS NULL").fetchone()[0]
    assert kopuk == 0, f"{kopuk} sonucun girişi yok"


# ------------------------------------------------------------ tick tekilliği
def test_ticks_tablosunda_tekrar_eden_kayit_yok(uretim_db):
    """KİLİT TEST — 2026-07-27'de ölçülen ve kapatılan arıza.

    `import_all` her koşumda tüm arşivi baştan okuyor; eski `insert_tick` düz
    INSERT olduğu için aynı gözlem her gün yeniden yazılıyordu. Ölçüm: dump'ta
    15 999 satır, tekil 1 663 (9.6×), en eski satır 23 kez. Onarım
    `db.tekil_tick_indeksi` ile yapıldı; bu test tekrarın geri gelmediğini
    dump üzerinde doğrular (indeks düşerse ya da import yolu değişirse düşer).
    """
    _, con, _ = uretim_db
    toplam = con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    tekil = con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT ts_utc, source, "
                        "symbol FROM ticks)").fetchone()[0]
    assert toplam == tekil, f"{toplam} tick satırının yalnız {tekil}'i tekil"


def test_dumptaki_insertler_or_ignore(uretim_db):
    """Dump geriye uyumlu olmalı: benzersiz indeks kurulduktan sonra düz
    `INSERT`'li bir dump'ı yüklemek `IntegrityError` üretir ve Actions'ın İLK
    adımı (restore) çöker — yani tüm üretim durur."""
    metin = DUMP.read_text(encoding="utf-8")
    assert "INSERT OR IGNORE INTO ticks(" in metin
    assert "\nINSERT INTO " not in metin, "düz INSERT kalmış (eski biçim)"


def test_dump_boyutu_makul(uretim_db):
    """Tekrar sızıntısının erken uyarısı: satır sayısı veri hacmiyle orantılı
    kalmalı. Tekilleştirme öncesi dump 33 699 satır / 4.98 MB idi; sonrası
    19 369 / 2.91 MB. Bu sınır veri büyüdükçe yükseltilebilir — ama iki katına
    fırlıyorsa önce "hangi tablo tekrar yazıyor?" diye bak."""
    _, _, sayilar = uretim_db
    satir = sum(1 for _ in DUMP.open(encoding="utf-8"))
    veri = sum(sayilar.values())
    assert satir < veri * 1.2 + 100, (
        f"dump {satir} satır ama yalnız {veri} kayıt var — tekrar sızıntısı?")


def test_tekil_tick_sayisi_tabanin_ustunde(uretim_db):
    """Tekrarlar bir gün temizlense bile TEKİL gözlem sayısı azalmamalı —
    L-009 kilit dişlisinin tick tarafı."""
    _, con, _ = uretim_db
    tekil = con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT ts_utc, source, "
                        "symbol FROM ticks)").fetchone()[0]
    assert tekil >= 1600, f"tekil tick gözlemi azalmış: {tekil}"
