"""Pazartesi mutabakat job'ı (rehber 1.3).

Hafta sonu prim noktaları prim_history'de zaten weekend=1 etiketli; bunlar
z-skor/backtest serisinden dışlanır (db.prim_series only_valid). Bu job hafta sonu
beklenti serisini pazartesi ilk GEÇERLİ prim ile karşılaştırıp raporlar.
"""
from __future__ import annotations

import logging

from . import db, util

log = logging.getLogger("reconcile")


def reconcile(cfg: dict) -> dict:
    con = db.connect(cfg)
    # mutabakat yapılmamış hafta sonu beklentileri
    rows = con.execute(
        "SELECT * FROM weekend_expectation WHERE reconciled=0 ORDER BY ts_utc"
    ).fetchall()
    if not rows:
        con.close()
        return {"reconciled": 0, "items": []}

    # pazartesi (forex açık) ilk geçerli prim
    valid = con.execute(
        "SELECT ts_utc, prim_pct FROM prim_history "
        "WHERE indicative=0 AND weekend=0 ORDER BY ts_utc DESC LIMIT 1"
    ).fetchone()
    realized = valid["prim_pct"] if valid else None

    items = []
    for r in rows:
        diff = None
        if realized is not None and r["expectation_pct"] is not None:
            diff = realized - r["expectation_pct"]
        items.append({
            "ts": r["ts_utc"],
            "beklenti_pct": r["expectation_pct"],
            "gerceklesen_pct": realized,
            "fark_puan": diff,
        })
        con.execute("UPDATE weekend_expectation SET reconciled=1 WHERE ts_utc=?",
                    (r["ts_utc"],))
    con.commit()
    con.close()
    log.info("mutabakat: %d hafta sonu noktası işlendi", len(items))
    return {"reconciled": len(items), "realized_prim": realized, "items": items}


if __name__ == "__main__":
    util.load_env()
    print(reconcile(util.load_config()))
