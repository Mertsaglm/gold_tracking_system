"""SQLite şeması ve erişim yardımcıları."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import util

log = logging.getLogger("db")

SCHEMA = """
-- (ts_utc, source, symbol) bir GÖZLEMİ tekil olarak tanımlar: ts_utc çekim anının
-- mikrosaniyeli damgasıdır ve bir CSV satırında her sembol bir kez geçer.
-- Tekillik BENZERSİZ İNDEKSLE zorlanıyor ama burada değil, `_tick_tekilligi()`
-- içinde: mevcut veritabanlarında tekrar eden satırlar var ve indeks önce onlar
-- temizlenmeden oluşturulamaz (bkz. o fonksiyonun docstring'i).
CREATE TABLE IF NOT EXISTS ticks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc    TEXT NOT NULL,
    source    TEXT NOT NULL,
    symbol    TEXT NOT NULL,
    buying    REAL,
    selling   REAL,
    raw       TEXT
);
CREATE INDEX IF NOT EXISTS idx_ticks_sym_ts ON ticks(symbol, ts_utc);

CREATE TABLE IF NOT EXISTS ohlc_1m (
    minute_utc TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    o REAL, h REAL, l REAL, c REAL, n INTEGER,
    PRIMARY KEY (minute_utc, symbol)
);

CREATE TABLE IF NOT EXISTS prim_history (
    ts_utc        TEXT PRIMARY KEY,
    ons_usd       REAL,
    usdtry        REAL,
    theoretical   REAL,
    market_has    REAL,
    gram_retail   REAL,
    prim_pct      REAL,          -- has bazlı (saflık düzeltmeli)
    prim_pct_naive REAL,         -- perakende gram ile (düzeltmesiz)
    spread_pct    REAL,
    quarter_prim_pct REAL,
    indicative    INTEGER,        -- 1 => sinyal dışı
    weekend       INTEGER,
    holiday       INTEGER,
    reason        TEXT
);

CREATE TABLE IF NOT EXISTS weekend_expectation (
    ts_utc            TEXT PRIMARY KEY,
    weekend_gram      REAL,
    frozen_theoretical REAL,
    expectation_pct   REAL,
    reconciled        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evds_daily (
    date        TEXT NOT NULL,
    series_code TEXT NOT NULL,
    value       REAL,
    PRIMARY KEY (date, series_code)
);

CREATE TABLE IF NOT EXISTS reports (
    date TEXT PRIMARY KEY,
    path TEXT,
    created_utc TEXT
);

CREATE TABLE IF NOT EXISTS history_daily (
    date        TEXT PRIMARY KEY,     -- ISO YYYY-MM-DD
    ons_usd     REAL,
    usdtry      REAL,
    gram_teorik REAL,
    ons_source  TEXT                  -- 'XAUUSD=X' | 'GC=F'
);

CREATE TABLE IF NOT EXISTS gld_tonnage (
    date   TEXT PRIMARY KEY,          -- ISO YYYY-MM-DD
    tonnes REAL
);

-- Günlük GERÇEK OHLC (Bölüm 6 — grafik yorumu). history_daily yalnız kapanış tutar ve
-- gram_teorik türetilmiş fiyattır; destek/direnç + hakiki ATR için yüksek/düşük şart.
-- Not: gram TL için OHLC TÜRETİLMEZ (high_ons × high_usd aynı ana ait değildir).
CREATE TABLE IF NOT EXISTS ohlc_daily (
    date   TEXT NOT NULL,             -- ISO YYYY-MM-DD (borsa yerel günü)
    symbol TEXT NOT NULL,             -- 'GC=F' (ons) | 'TRY=X' (kur)
    o REAL, h REAL, l REAL, c REAL,
    v REAL,                           -- TRY=X'te 0; GC=F'te ön-vade kontrat hacmi (GÜVENİLMEZ)
    source TEXT,                      -- 'yfinance'
    PRIMARY KEY (date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_ohlcd_sym_date ON ohlc_daily(symbol, date);

-- ---------- Tahmin kaydı (Bölüm 8 — karar motoru karnesi) ----------
-- Sistemin verdiği HER hüküm buraya yazılır ve vadesi gelince otomatik çözülür.
-- Bu tablo projenin dürüstlük altyapısıdır: hüküm net olabilir çünkü karnesi
-- tutuluyor. Karne olmadan "AL" demek kehanettir; karneyle birlikte iddiadır.
CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc     TEXT NOT NULL,
    model_version   TEXT NOT NULL,   -- değişirse canlı karne SIFIRLANIR: farklı
                                     -- modelin tahminleri aynı karnede toplanamaz
    kaynak          TEXT NOT NULL,   -- 'canli' | 'replay'
    asof_date       TEXT NOT NULL,   -- SON TAM KAPANMIŞ gün (T-1); özellik kesimi
    horizon_days    INTEGER NOT NULL,
    target_date     TEXT NOT NULL,
    kol             TEXT NOT NULL,   -- 'cekirdek' | 'taktik'
    hukum           TEXT NOT NULL,
    skor            REAL,            -- REZERVE: hiçbir kol şu an skor üretmiyor
                                     -- (ADR #007-D ağırlık öğrenmeyi reddetti).
                                     -- Üretici bağlanana dek daima NULL.
    guven           TEXT,            -- "düşük"|"orta"|"yüksek". REAL idi ve insert
                                     -- sabit None geçiyordu: hüküm hangi güvenle
                                     -- verildi denetimde okunamıyordu.
    beklenen_gram_kazanc_pct REAL,   -- bkz. karar.taktik_hukum: üretici YOK
    esik_pct        REAL,            -- o an geçerli engel (taban + maliyet)
    kapi_acik       INTEGER NOT NULL,-- 0 → hüküm SAT olsa bile TUT'a kilitlendi
    ozellikler_json TEXT NOT NULL,
    UNIQUE(model_version, kaynak, asof_date, horizon_days, kol)
);
CREATE INDEX IF NOT EXISTS idx_pred_target ON predictions(target_date, kaynak);

-- Giriş fiyatı AYRI tabloda: asof=T-1'de hüküm verilir ama giriş T'nin
-- kapanışıdır ve o an HENÜZ BİLİNMEZ. Aynı satıra yazmak look-ahead olurdu.
CREATE TABLE IF NOT EXISTS prediction_entries (
    prediction_id     INTEGER PRIMARY KEY REFERENCES predictions(id),
    giris_date        TEXT NOT NULL,
    giris_gram_teorik REAL NOT NULL,  -- 3 işlem günü ort. (çıkışla SİMETRİK)
    doldurma_utc      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    prediction_id         INTEGER PRIMARY KEY REFERENCES predictions(id),
    cozum_utc             TEXT NOT NULL,
    cikis_date            TEXT NOT NULL,
    cikis_gram_teorik     REAL NOT NULL,  -- hedef ±1 gün, 3 gün ortalaması
    mevduat_yillik_pct    REAL,
    gram_carry_kazanc_pct REAL NOT NULL,  -- (giris/cikis)×(1+net_faiz) − 1
    roundtrip_maliyet_pct REAL NOT NULL,
    hukum_dogru           INTEGER NOT NULL,
    taban_dogru           INTEGER NOT NULL, -- "hep TUT" aynı pencerede doğru muydu
    gram_etkisi_pct       REAL NOT NULL
);

-- Karneyi güzelleştirmek için geçmiş bir tahmini "düzeltmek" kaçınılmaz bir
-- ayartıdır ("şu tahmin bozuktu, elle düzelteyim"). Şema bunu imkânsız kılar.
--
-- DROP + CREATE (IF NOT EXISTS değil): trigger'ın TANIMI değiştiğinde
-- `IF NOT EXISTS` eski tanımı olduğu gibi bırakır ve koruma sessizce eski
-- kapsamda kalır. Her bağlantıda yeniden kurmak, kodda yazan kapsamın
-- gerçekten yürürlükte olmasını garanti eder (L-011: kâğıt üstünde koruma).
--
-- `kaynak` ve `model_version` de listede: bir tahminin HANGİ karneye sayıldığını
-- tam olarak bu iki kolon belirliyor. kaynak='replay' → 'canli' yapılırsa
-- tahmin_backfill'in 458 haftalık replay'i canlı karneye karışır; oysa ADR
-- #007-H o modülün "karne ÜRETMEZ" olduğunu özellikle yazıyor.
DROP TRIGGER IF EXISTS trg_predictions_immutable;
CREATE TRIGGER trg_predictions_immutable
BEFORE UPDATE OF hukum, skor, guven, ozellikler_json, asof_date, esik_pct,
                 kapi_acik, horizon_days, target_date, kol,
                 kaynak, model_version
ON predictions
BEGIN
    SELECT RAISE(ABORT, 'tahmin kaydi degistirilemez');
END;

-- Karneyi güzelleştirmenin en kısa yolu kötü tahmini "düzeltmek" DEĞİL, SİLMEKTİR.
-- UPDATE'i engelleyip DELETE'i serbest bırakmak, kilidi takıp kapıyı açık
-- bırakmaktır. Restore yolu satır silmiyor (dosyayı silip şemayı yeniden kuruyor),
-- yani bu trigger hiçbir meşru akışı engellemez.
DROP TRIGGER IF EXISTS trg_predictions_nodelete;
CREATE TRIGGER trg_predictions_nodelete
BEFORE DELETE ON predictions
BEGIN
    SELECT RAISE(ABORT, 'tahmin kaydi silinemez');
END;
"""


TICK_TEKIL_INDEKS = "idx_ticks_uniq"


def tekil_tick_indeksi(con) -> int:
    """`ticks` tablosuna benzersiz indeksi kurar; gerekiyorsa önce onarır.

    NEDEN VAR — ölçülmüş bir arıza (2026-07-27): `import_actions.import_all` her
    `daily_job` koşumunda TÜM arşiv CSV'lerini baştan okuyor ve eski `insert_tick`
    düz `INSERT` olduğu için aynı gözlemi her gün yeniden yazıyordu. Üretim
    dump'ında 15 999 tick satırının yalnız 1 663'ü tekildi (9.6×); en eski satır
    23 kez yazılmıştı. İki zararı vardı:
      1. `data/altin.sql` her gün ~1663 satır büyüyordu — diff'lenebilir dump'ın
         var olma sebebi olan repo şişmesi geri geliyordu (Faz 5 kararı).
      2. Raporun "Ham tick: N" satırı veri hacmini değil KOŞUM SAYISINI ölçüyordu:
         girdiden bağımsız büyüyen bir sayı, ölçüm kılığında bir sayaçtır (L-010).

    Onarım güvenli: tekrar eden satırlar BİREBİR aynı (aynı anahtarda farklı değer
    taşıyan tek bir satır bile yok — 2026-07-27 ölçümü), yani silinen kopyalar
    hiçbir bilgi taşımıyor. En küçük `id` korunur.

    Neden `SCHEMA` içinde değil: mevcut veritabanlarında kopyalar dururken
    `CREATE UNIQUE INDEX` hata verir ve `connect()` çağıran HER komut patlardı.
    Önce temizleyip sonra kurmak, koruma yolunu kendi kendini onarır kılıyor.
    """
    var = con.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                      (TICK_TEKIL_INDEKS,)).fetchone()
    if var:
        return 0
    silinen = con.execute(
        "DELETE FROM ticks WHERE id NOT IN "
        "(SELECT MIN(id) FROM ticks GROUP BY ts_utc, source, symbol)").rowcount
    con.execute(f"CREATE UNIQUE INDEX {TICK_TEKIL_INDEKS} "
                "ON ticks(ts_utc, source, symbol)")
    con.commit()
    if silinen:
        log.info("ticks onarildi: %d tekrar eden satir silindi", silinen)
    return max(0, silinen)


def connect(cfg: dict, tekillestir: bool = True) -> sqlite3.Connection:
    """Bağlantı + şema. `tekillestir=False` YALNIZ restore içindir.

    Restore, dump'ı okurken benzersiz indeksin HENÜZ kurulmamış olmasını ister:
    2026-07-27 öncesi üretilmiş dump'lar düz `INSERT` ve tekrar eden `ticks`
    satırları içeriyor; indeks önce kurulursa eski bir commit'e dönüp
    `python -m src.restore_db` çalıştırmak `IntegrityError` ile patlardı.
    Yükleme bitince `tekil_tick_indeksi()` çağrılır ve sonuç her iki dump
    biçiminde de aynı olur: tekil veri + kurulu indeks.
    """
    path = util.abspath(cfg["paths"]["db"])
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(SCHEMA)
    if tekillestir:
        tekil_tick_indeksi(con)
    return con


def insert_tick(con, ts_utc: str, source: str, symbol: str,
                buying: Optional[float], selling: Optional[float],
                raw: str = "") -> int:
    """Bir gözlemi yazar; AYNI gözlem ikinci kez yazılmaz (bkz. `_tick_tekilligi`).

    Gerçekten eklenen satır sayısını döner (0 = zaten vardı). Çağıran bu değere
    bakarak yalnız YENİ veriyi işlemeli — yoksa `ohlc_1m`'in örnek sayacı (`n`)
    her yeniden okumada şişer.
    """
    return con.execute(
        "INSERT OR IGNORE INTO ticks(ts_utc,source,symbol,buying,selling,raw) "
        "VALUES(?,?,?,?,?,?)",
        (ts_utc, source, symbol, buying, selling, raw),
    ).rowcount


def update_ohlc(con, minute_utc: str, symbol: str, price: float) -> None:
    row = con.execute(
        "SELECT o,h,l,c,n FROM ohlc_1m WHERE minute_utc=? AND symbol=?",
        (minute_utc, symbol),
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO ohlc_1m(minute_utc,symbol,o,h,l,c,n) VALUES(?,?,?,?,?,?,1)",
            (minute_utc, symbol, price, price, price, price),
        )
    else:
        con.execute(
            "UPDATE ohlc_1m SET h=?,l=?,c=?,n=? WHERE minute_utc=? AND symbol=?",
            (max(row["h"], price), min(row["l"], price), price, row["n"] + 1,
             minute_utc, symbol),
        )


def insert_prim(con, **kw) -> None:
    cols = ("ts_utc", "ons_usd", "usdtry", "theoretical", "market_has", "gram_retail",
            "prim_pct", "prim_pct_naive", "spread_pct", "quarter_prim_pct",
            "indicative", "weekend", "holiday", "reason")
    con.execute(
        f"INSERT OR REPLACE INTO prim_history({','.join(cols)}) "
        f"VALUES({','.join('?' * len(cols))})",
        tuple(kw.get(c) for c in cols),
    )


def insert_weekend_exp(con, ts_utc, weekend_gram, frozen_theoretical, expectation_pct) -> None:
    con.execute(
        "INSERT OR REPLACE INTO weekend_expectation"
        "(ts_utc,weekend_gram,frozen_theoretical,expectation_pct) VALUES(?,?,?,?)",
        (ts_utc, weekend_gram, frozen_theoretical, expectation_pct),
    )


def prim_series(con, column: str = "prim_pct") -> list[float]:
    """Z-skor için tarihsel prim serisi — DAİMA yalnız geçerli kayıtlar.

    `only_valid` diye bir anahtar vardı; sekiz çağıranın sekizi de `True`
    geçiyordu, yani `False` yolu hiç koşulmamış ölü bir daldı. Geçersiz
    (indicative / hafta sonu) kayıtları z-skor tabanına katmak zaten kuralın
    ihlali olurdu — seçenek olarak durması yanlış kullanıma davetiyeydi.

    Not: `weekend=0` koşulu `indicative=0` altında teknik olarak fazlalık
    (hafta sonu kayıtları zaten indicative işaretlenir) ama ikisi ayrı
    sütunlarda tutulduğu için açıkça yazılıyor — biri bozulursa diğeri korur.
    """
    return [r[0] for r in con.execute(
        f"SELECT {column} FROM prim_history "
        f"WHERE {column} IS NOT NULL AND indicative=0 AND weekend=0 "
        "ORDER BY ts_utc").fetchall()]


def latest_prim(con) -> Optional[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM prim_history ORDER BY ts_utc DESC LIMIT 1"
    ).fetchone()


def last_tick_time(con, symbol: str) -> Optional[datetime]:
    row = con.execute(
        "SELECT ts_utc FROM ticks WHERE symbol=? ORDER BY ts_utc DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    if row is None:
        return None
    return datetime.fromisoformat(row["ts_utc"]).astimezone(timezone.utc)


def count_valid_prim(con) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM prim_history WHERE indicative=0 AND weekend=0"
    ).fetchone()[0]


def count_valid_prim_days(con) -> int:
    """Geçerli prim arşivinin kapsadığı farklı gün sayısı.

    Z-skor kapısı bunu sayar, kaydı değil: gün içinde ~10 örnek alınıyor ve bunlar
    birbirinin tekrarı (otokorelasyon). Kayıt saymak bağımsız gözlem sayısını
    olduğundan büyük gösterir; z-skorun dağılım tabanı gün cinsindendir.
    """
    return con.execute(
        "SELECT COUNT(DISTINCT date(ts_utc)) FROM prim_history "
        "WHERE indicative=0 AND weekend=0"
    ).fetchone()[0]


def prim_daily_means(con, column: str = "prim_pct") -> list[tuple[str, float]]:
    """Geçerli primin GÜNLÜK ortalaması: [(tarih, ortalama)].

    Kapı gün sayarken (count_valid_prim_days) z-skorun dağılım tabanı da gün
    cinsinden olmalı; gün içi ~10 örnek birbirinin tekrarıdır ve std'yi
    otokorelasyonlu gürültüyle bozar. Kuru prova iki tabanı karşılaştırır
    (bkz. signals.zscore_dry_run).
    """
    rows = con.execute(
        f"SELECT date(ts_utc) d, AVG({column}) FROM prim_history "
        f"WHERE {column} IS NOT NULL AND indicative=0 AND weekend=0 "
        "GROUP BY d ORDER BY d"
    ).fetchall()
    return [(r[0], r[1]) for r in rows]
