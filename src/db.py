"""SQLite şeması ve erişim yardımcıları."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import util

SCHEMA = """
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
"""


def connect(cfg: dict) -> sqlite3.Connection:
    path = util.abspath(cfg["paths"]["db"])
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(SCHEMA)
    return con


def insert_tick(con, ts_utc: str, source: str, symbol: str,
                buying: Optional[float], selling: Optional[float], raw: str = "") -> None:
    con.execute(
        "INSERT INTO ticks(ts_utc,source,symbol,buying,selling,raw) VALUES(?,?,?,?,?,?)",
        (ts_utc, source, symbol, buying, selling, raw),
    )


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


def prim_series(con, only_valid: bool = True, column: str = "prim_pct") -> list[float]:
    """Z-skor için tarihsel prim serisi. only_valid: hafta sonu/indicative hariç."""
    q = f"SELECT {column} FROM prim_history WHERE {column} IS NOT NULL"
    if only_valid:
        q += " AND indicative=0 AND weekend=0"
    q += " ORDER BY ts_utc"
    return [r[0] for r in con.execute(q).fetchall()]


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
