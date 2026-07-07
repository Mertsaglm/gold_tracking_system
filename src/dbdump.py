"""Bölüm 2 — Repo şişme önlemi: SQLite'ı diff'lenebilir SQL text dump'a çevirir.

git binary DB'nin her sürümünü tam saklar → geçmiş şişer. Bunun yerine deterministik
(mantıksal anahtara göre sıralı) SQL text dump commit'lenir; günlük diff = yalnız yeni satırlar.

- dump: data/altin.sql üretir (yalnız INSERT'ler; şema koddan gelir).
- restore: SQLite'ı dump'tan yeniden kurar (python -m src.restore_db ile de çağrılır).
"""
from __future__ import annotations

import logging
import sqlite3

from . import db, util

log = logging.getLogger("dbdump")

# (tablo, sıralama anahtarı, hariç tutulan kolonlar) — deterministik diff için
_TABLES = [
    ("ticks", "ts_utc, source, symbol, buying, selling", ["id"]),
    ("ohlc_1m", "minute_utc, symbol", []),
    ("prim_history", "ts_utc", []),
    ("weekend_expectation", "ts_utc", []),
    ("evds_daily", "series_code, date", []),
    ("reports", "date", []),
    ("history_daily", "date", []),
    ("gld_tonnage", "date", []),
]


def _sql_val(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def dump(cfg: dict, out_path: str | None = None) -> str:
    con = db.connect(cfg)
    con.row_factory = sqlite3.Row
    lines = ["-- Altin DB dump (deterministik, diff'lenebilir). Sema koddan gelir.",
             "-- Restore: python -m src.restore_db", ""]
    for table, order, exclude in _TABLES:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()
                if r[1] not in exclude]
        collist = ", ".join(cols)
        rows = con.execute(f"SELECT {collist} FROM {table} ORDER BY {order}").fetchall()
        lines.append(f"-- {table}: {len(rows)} satır")
        for r in rows:
            vals = ", ".join(_sql_val(r[c]) for c in cols)
            lines.append(f"INSERT INTO {table}({collist}) VALUES({vals});")
        lines.append("")
    con.close()
    text = "\n".join(lines)
    path = util.abspath(out_path or cfg["paths"].get("db_dump", "data/altin.sql"))
    path.write_text(text, encoding="utf-8")
    log.info("dump yazıldı: %s (%d satır)", path, text.count("INSERT INTO"))
    return str(path)


def restore(cfg: dict, dump_path: str | None = None) -> dict:
    """Dump'tan SQLite'ı yeniden kurar. Mevcut DB silinir, şema+veri baştan."""
    dbfile = util.abspath(cfg["paths"]["db"])
    dpath = util.abspath(dump_path or cfg["paths"].get("db_dump", "data/altin.sql"))
    if not dpath.exists():
        log.warning("dump yok: %s — boş DB ile devam", dpath)
        con = db.connect(cfg)
        con.close()
        return {"restored": False}
    # eski DB'yi kaldır (WAL/SHM dahil)
    for suffix in ("", "-wal", "-shm"):
        p = dbfile.parent / (dbfile.name + suffix)
        if p.exists():
            p.unlink()
    con = db.connect(cfg)                       # şemayı oluşturur
    con.executescript(dpath.read_text(encoding="utf-8"))
    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t, _, _ in _TABLES}
    con.close()
    log.info("restore tamam: %s", counts)
    return {"restored": True, "counts": counts}


if __name__ == "__main__":
    import sys
    util.load_env()
    cfg = util.load_config()
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        print(restore(cfg))
    else:
        print(dump(cfg))
