"""DB şeması ↔ dump SÖZLEŞMESİ — Actions stateless olduğu için hayat memat meselesi.

Bu projede SQLite **kalıcı değil**: `data/altin.sqlite` gitignore'da, her Actions
koşumu DB'yi `data/altin.sql` dump'ından yeniden kuruyor (`daily.yml`:
`restore_db` → iş → `dbdump`). Sonuç: **dump'a girmeyen tablo her gün silinir.**

Bu yüzden "yeni tablo ekledim" ile "yeni tablo yaşıyor" aynı şey değildir. Bir
tabloyu `db.SCHEMA`'ya ekleyip `dbdump._TABLES`'a eklemeyi unutmak, hiçbir hata
üretmeden veriyi her gün sıfırlar — ve tablo yerelde çalıştığı için fark
edilmez. `predictions` için bu, KARNENİN her gün sıfırlanması demek olurdu
(dbdump.py yorumu bunu açıkça yazıyor).

İkinci konu: `predictions` DEĞİŞTİRİLEMEZLİĞİ (ADR #007-F). Karneyi
güzelleştirmek için geçmiş bir tahmini "düzeltmek" kaçınılmaz bir ayartıdır ve
disiplinle değil İMKÂNSIZLIKLA çözülür. Buradaki testler o imkânsızlığın
kapsamını kolon kolon ölçer.

2026-07-27'de kapsam iki yönden genişletildi (denetimde bulunan açıklar):
  - **DELETE** engellenmiyordu; oysa karneyi güzelleştirmenin en kısa yolu kötü
    tahmini düzeltmek değil SİLMEKTİR.
  - `kaynak` ve `model_version` trigger listesinde yoktu; bir tahminin HANGİ
    karneye sayıldığını tam olarak bu iki kolon belirliyor.
"""
from __future__ import annotations

import pathlib
import sqlite3

import pytest

from src import db, dbdump

# Trigger'ın koruduğu kolonlar (db.SCHEMA'daki BEFORE UPDATE OF listesi).
KORUNAN_KOLONLAR = ("hukum", "skor", "guven", "ozellikler_json", "asof_date",
                    "esik_pct", "kapi_acik", "horizon_days", "target_date", "kol",
                    "kaynak", "model_version")

SQLITE_IC = {"sqlite_sequence"}


def _sema_con():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(db.SCHEMA)
    return con


def _sema_tablolari() -> set[str]:
    con = _sema_con()
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")} - SQLITE_IC
    finally:
        con.close()


def _kolonlar(con, tablo) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({tablo})").fetchall()]


DUMP_TABLOLARI = {t for t, _, _ in dbdump._TABLES}


# ---------------------------------------------------------- dump kapsaması
def test_her_sema_tablosu_dumpta():
    """KİLİT TEST. Dump'a girmeyen tablo Actions'ta her gün silinir.

    Yeni bir tablo eklendiğinde bu test düşer ve `dbdump._TABLES`'a eklemeyi
    hatırlatır. Bilerek dışarıda bırakılacaksa gerekçesi buraya yazılmalı —
    sessiz bir eksiklik "veri var sanıyordum" ile sonuçlanır.
    """
    eksik = _sema_tablolari() - DUMP_TABLOLARI
    assert not eksik, (f"şemada olup dump'a girmeyen tablolar: {sorted(eksik)} — "
                       "Actions her koşumda dump'tan restore ediyor, bu tablolar "
                       "her gün SIFIRLANIR (dbdump._TABLES'a ekle)")


def test_dumpta_olmayan_tablo_dumplanmiyor():
    """Ters yön: `_TABLES`'ta şemada olmayan tablo varsa dump çöker."""
    fazla = DUMP_TABLOLARI - _sema_tablolari()
    assert not fazla, f"şemada olmayan tablolar dumplanıyor: {sorted(fazla)}"


def test_dump_siralama_anahtarlari_gercek_kolon():
    """`ORDER BY` kolonu yoksa dump `OperationalError` ile patlar → commit'lenen
    dump eskisi kalır ve veri sessizce donar."""
    con = _sema_con()
    try:
        for tablo, siralama, _ in dbdump._TABLES:
            mevcut = set(_kolonlar(con, tablo))
            for k in (x.strip() for x in siralama.split(",")):
                assert k in mevcut, f"{tablo}: ORDER BY {k} — böyle bir kolon yok"
    finally:
        con.close()


def test_dump_tum_kolonlari_tasir():
    """Hariç tutulan kolon dışında HER kolon dump'a girer.

    Bir kolon eklenip dump'a girmezse: yerelde dolu, üretimde her gün NULL.
    """
    con = _sema_con()
    try:
        for tablo, _, haric in dbdump._TABLES:
            tasinan = [k for k in _kolonlar(con, tablo) if k not in haric]
            assert set(tasinan) == set(_kolonlar(con, tablo)) - set(haric)
            assert tasinan, f"{tablo}: hiç kolon taşınmıyor"
    finally:
        con.close()


def test_yalnizca_ticks_id_haric_predictions_id_DAHIL():
    """ADR #007-F: `predictions.id` dump'a GİRMEK ZORUNDA.

    `prediction_entries/outcomes` ona referans veriyor. Hariç tutulsaydı
    restore'da yeni id'ler atanır ve giriş/sonuç bağları sessizce kopardı —
    "tahmin var, karnesi yok" durumu. `ticks.id` ise AUTOINCREMENT bir yüzey
    kimliği; kimse referans vermiyor, diff gürültüsü olmasın diye dışarıda.
    """
    haric = {t: set(h) for t, _, h in dbdump._TABLES}
    assert haric["ticks"] == {"id"}
    assert haric["predictions"] == set(), "predictions.id hariç tutulmuş → bağlar kopar"
    for tablo, kume in haric.items():
        if tablo != "ticks":
            assert not kume, f"{tablo}: beklenmeyen hariç tutma {kume}"


def test_tahmin_zinciri_dump_restore_sonrasi_ayakta(izole_kok):
    """KİLİT TEST — Actions'ın her gün yaptığı şeyin birebir provası.

    kaydet → dump → (DB sil) → restore → JOIN hâlâ çalışıyor mu?
    `predictions.id` dump'tan çıkarılırsa bu test düşer.
    """
    cfg, _ = izole_kok
    con = db.connect(cfg)
    con.execute(
        "INSERT INTO predictions(created_utc,model_version,kaynak,asof_date,"
        "horizon_days,target_date,kol,hukum,guven,kapi_acik,ozellikler_json) "
        "VALUES('t','v1.0','canli','2026-01-05',5,'2026-01-12','taktik','TUT',"
        "'yüksek',0,'{}')")
    pid = con.execute("SELECT id FROM predictions").fetchone()[0]
    con.execute("INSERT INTO prediction_entries(prediction_id,giris_date,"
                "giris_gram_teorik,doldurma_utc) VALUES(?,?,?,?)",
                (pid, "2026-01-06", 6000.0, "t"))
    con.execute(
        "INSERT INTO prediction_outcomes(prediction_id,cozum_utc,cikis_date,"
        "cikis_gram_teorik,gram_carry_kazanc_pct,roundtrip_maliyet_pct,"
        "hukum_dogru,taban_dogru,gram_etkisi_pct) "
        "VALUES(?,?,?,?,?,?,?,?,?)", (pid, "t", "2026-01-13", 6100.0, -1.6, 1.2, 1, 1, 0.0))
    con.commit()
    con.close()

    dbdump.dump(cfg)
    sonuc = dbdump.restore(cfg)
    assert sonuc["restored"] is True

    con = db.connect(cfg)
    try:
        satir = con.execute(
            "SELECT p.hukum, e.giris_gram_teorik, o.gram_etkisi_pct FROM predictions p "
            "JOIN prediction_entries e ON e.prediction_id=p.id "
            "JOIN prediction_outcomes o ON o.prediction_id=p.id").fetchall()
        assert len(satir) == 1, "restore sonrası tahmin↔giriş↔sonuç bağı koptu"
        assert satir[0]["hukum"] == "TUT"
    finally:
        con.close()


def test_restore_dump_yoksa_bos_db_ile_devam(izole_kok):
    """İlk kurulumda dump yok; restore çökmemeli (Actions ilk koşumu)."""
    cfg, _ = izole_kok
    assert dbdump.restore(cfg) == {"restored": False}


def test_sema_iki_kez_uygulanabilir(izole_kok):
    """`db.connect` her çağrıda SCHEMA'yı çalıştırıyor (CREATE IF NOT EXISTS).
    Bir gün `IF NOT EXISTS` düşerse ikinci bağlantı patlar — ve neredeyse her
    fonksiyon ikinci bağlantı açıyor."""
    cfg, _ = izole_kok
    for _ in range(3):
        con = db.connect(cfg)
        con.execute("INSERT OR REPLACE INTO history_daily(date,gram_teorik) "
                    "VALUES('2026-01-01',6000)")
        con.commit()
        con.close()
    con = db.connect(cfg)
    try:
        assert con.execute("SELECT COUNT(*) FROM history_daily").fetchone()[0] == 1
    finally:
        con.close()


# ---------------------------------------------------------- değiştirilemezlik
@pytest.mark.parametrize("kolon", KORUNAN_KOLONLAR)
def test_tahmin_kolonu_degistirilemez(izole_kok, kolon):
    """ADR #007-F: dokuz kolonun HER BİRİ ayrı ayrı kilitli olmalı.

    Mevcut test yalnız `hukum`'u deniyordu; trigger'ın kolon listesinden bir ad
    düşse (ör. `kapi_acik`) hiçbir test bunu görmezdi. Oysa `kapi_acik`
    değiştirilebilirse "kapı kapalıydı" kaydı sonradan "açıktı"ya çevrilir ve
    karne yeniden yorumlanır.
    """
    cfg, _ = izole_kok
    con = db.connect(cfg)
    try:
        con.execute(
            "INSERT INTO predictions(created_utc,model_version,kaynak,asof_date,"
            "horizon_days,target_date,kol,hukum,kapi_acik,ozellikler_json) "
            "VALUES('t','v1.0','canli','2026-01-05',5,'2026-01-12','taktik',"
            "'TUT',0,'{}')")
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(f"UPDATE predictions SET {kolon}=? WHERE id=1", (0,))
    finally:
        con.close()


def test_predictions_unique_kisiti_ayni_gunu_iki_kez_yazmaz(izole_kok):
    """`daily_job` aynı gün iki kez koşabilir (workflow_dispatch). UNIQUE kısıtı
    olmadan aynı asof için iki hüküm yazılır ve karne çift sayardı."""
    cfg, _ = izole_kok
    con = db.connect(cfg)
    try:
        sql = ("INSERT OR IGNORE INTO predictions(created_utc,model_version,kaynak,"
               "asof_date,horizon_days,target_date,kol,hukum,kapi_acik,"
               "ozellikler_json) VALUES('t','v1.0','canli','2026-01-05',5,"
               "'2026-01-12','taktik','TUT',0,'{}')")
        con.execute(sql)
        con.execute(sql)
        con.commit()
        assert con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 1
    finally:
        con.close()


def test_prim_istatistik_fonksiyonlari_gecersizleri_disliyor():
    """`prim_history`'nin İSTATİSTİK tabanı daima `indicative=0 AND weekend=0`.

    Bu kural ADR #008-G'de "var olan kural" diye anılıyor ve `ohlc_daily`'de
    eksik olduğu için hayalet bar sorunu doğdu. Dört fonksiyonun sorgu metni
    doğrudan denetlenir: filtreyi kaldırmak z-skor tabanına hafta sonu/bayat
    kayıtları katar ve eşik sessizce kayar.
    """
    import inspect
    for fn in (db.prim_series, db.count_valid_prim, db.count_valid_prim_days,
               db.prim_daily_means):
        kaynak = inspect.getsource(fn)
        assert "indicative=0" in kaynak, f"{fn.__name__}: indicative filtresi yok"
        assert "weekend=0" in kaynak, f"{fn.__name__}: weekend filtresi yok"


def test_tahmin_kaydi_SILINEMEZ(izole_kok):
    """KİLİT TEST. UPDATE'i engelleyip DELETE'i serbest bırakmak, kilidi takıp
    kapıyı açık bırakmaktır.

    Karneyi güzelleştirmenin en kısa yolu kötü tahmini "düzeltmek" değil
    SİLMEKTİR; ADR #007-F'nin "disiplinle değil imkânsızlıkla çözülür" iddiası
    ancak iki yol da kapalıyken doğru. Restore satır silmiyor (dosyayı silip
    şemayı yeniden kuruyor), yani bu trigger meşru hiçbir akışı engellemez.
    """
    cfg, _ = izole_kok
    con = db.connect(cfg)
    try:
        con.execute(
            "INSERT INTO predictions(created_utc,model_version,kaynak,asof_date,"
            "horizon_days,target_date,kol,hukum,kapi_acik,ozellikler_json) "
            "VALUES('t','v1.0','canli','2026-01-05',5,'2026-01-12','taktik',"
            "'TUT',0,'{}')")
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("DELETE FROM predictions WHERE id=1")
        con.rollback()
        assert con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 1
    finally:
        con.close()


def test_replay_tahmini_canli_karneye_aklanamiyor(izole_kok):
    """KİLİT TEST. `kaynak` ve `model_version` bir tahminin HANGİ karneye
    sayıldığını belirliyor.

    `tahmin_backfill` 458 haftalık replay üretiyor ve ADR #007-H o modülün
    "karne ÜRETMEZ" olduğunu özellikle yazıyor ("10.5 yıllık replay'e 'işte
    karnem' demek cazipti ama sahte olurdu"). Tek bir UPDATE ile `replay` →
    `canli` çevirmek o cümleyi geçersiz kılardı — artık şema engelliyor.
    """
    from src import tahmin, util
    cfg, _ = izole_kok
    con = db.connect(cfg)
    try:
        con.execute(
            "INSERT INTO predictions(created_utc,model_version,kaynak,asof_date,"
            "horizon_days,target_date,kol,hukum,kapi_acik,ozellikler_json) "
            "VALUES('t','v1.0','replay','2020-01-06',21,'2020-02-03','taktik',"
            "'SAT_25',0,'{}')")
        con.commit()
        for kolon, deger in (("kaynak", "canli"), ("model_version", "v9.9")):
            with pytest.raises(sqlite3.IntegrityError):
                con.execute(f"UPDATE predictions SET {kolon}=? WHERE id=1", (deger,))
            con.rollback()
        # canlı karne bu satırı görmemeye devam ediyor
        assert tahmin.karne(cfg, con)["cozulmus"] == 0
        assert tahmin.karne(cfg, con)["bekleyen"] == 0
    finally:
        con.close()


# ---------------------------------------------------------- ticks tekilliği
def test_ticks_benzersiz_indeksi_kuruluyor(izole_kok):
    """2026-07-27 onarımı: aynı gözlem iki kez yazılamaz.

    Kopyalar sessizdi ve iki şeyi birden bozuyordu: dump her gün ~1663 satır
    büyüyordu (repo şişmesi — dbdump'ın var olma sebebi) ve raporun "Ham tick"
    metriği veri hacmi yerine KOŞUM SAYISINI ölçüyordu (L-010).
    """
    cfg, _ = izole_kok
    con = db.connect(cfg)
    try:
        assert con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (db.TICK_TEKIL_INDEKS,)).fetchone(), "benzersiz indeks kurulmamış"
        assert db.insert_tick(con, "2026-07-23T10:00:00+00:00", "gh_actions",
                              "gram_has_altin", 6000.0, 6001.0) == 1
        assert db.insert_tick(con, "2026-07-23T10:00:00+00:00", "gh_actions",
                              "gram_has_altin", 6000.0, 6001.0) == 0
        # farklı sembol / farklı an ayrı gözlemdir
        assert db.insert_tick(con, "2026-07-23T10:00:00+00:00", "gh_actions",
                              "usd", 46.9, 47.0) == 1
        assert db.insert_tick(con, "2026-07-23T10:15:00+00:00", "gh_actions",
                              "gram_has_altin", 6000.0, 6001.0) == 1
        con.commit()
        assert con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == 3
    finally:
        con.close()


def test_eski_veritabani_kendini_onariyor(izole_kok):
    """Onarım KENDİ KENDİNE koşmalı: mevcut DB'lerde kopyalar var ve indeks
    onlar temizlenmeden kurulamaz. `connect` bunu bir kez yapıp geçer."""
    cfg, _ = izole_kok
    ham = db.connect(cfg, tekillestir=False)
    ham.execute(f"DROP INDEX IF EXISTS {db.TICK_TEKIL_INDEKS}")
    for _ in range(5):                                   # eski davranış: düz INSERT
        ham.execute("INSERT INTO ticks(ts_utc,source,symbol,buying,selling,raw) "
                    "VALUES('2026-07-23T10:00:00+00:00','gh_actions','usd',46.9,47.0,'')")
    ham.commit()
    assert ham.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == 5
    ham.close()

    con = db.connect(cfg)                                # onarım burada koşar
    try:
        assert con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == 1
        assert db.insert_tick(con, "2026-07-23T10:00:00+00:00", "gh_actions",
                              "usd", 46.9, 47.0) == 0
    finally:
        con.close()


def test_dump_restore_eski_bicimli_kopyali_dumpu_da_yukluyor(izole_kok):
    """Geriye uyum: 2026-07-27 öncesi dump'lar düz `INSERT` ve kopya içeriyor.
    `git checkout <eski commit>` + `restore_db` patlamamalı — indeks yükleme
    BİTTİKTEN sonra kuruluyor."""
    cfg, kok = izole_kok
    yol = kok / "eski.sql"
    satir = ("INSERT INTO ticks(ts_utc, source, symbol, buying, selling, raw) "
             "VALUES('2026-07-23T10:00:00+00:00', 'gh_actions', 'usd', 46.9, 47.0, '');")
    yol.write_text("\n".join([satir] * 4), encoding="utf-8")
    sonuc = dbdump.restore(cfg, dump_path=str(yol))
    assert sonuc["restored"] is True
    assert sonuc["counts"]["ticks"] == 1, "kopyalar temizlenmedi"


def test_yeni_dump_or_ignore_kullaniyor(izole_kok):
    """Dump'ın kendisi de geriye uyumlu olmalı: benzersiz indeks kurulduktan
    sonra düz INSERT'li bir dump'ı yüklemek `IntegrityError` üretirdi."""
    cfg, _ = izole_kok
    con = db.connect(cfg)
    db.insert_tick(con, "2026-07-23T10:00:00+00:00", "gh_actions", "usd", 46.9, 47.0)
    con.commit()
    con.close()
    metin = pathlib.Path(dbdump.dump(cfg)).read_text(encoding="utf-8")
    assert "INSERT OR IGNORE INTO ticks(" in metin
    assert "\nINSERT INTO " not in metin
