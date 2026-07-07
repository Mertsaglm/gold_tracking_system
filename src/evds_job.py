"""EVDS backfill + günlük güncelleme + rapor bağlam sağlayıcı.

- backfill: config'teki 'backfill' listesindeki serilerin tüm geçmişini evds_daily'ye çeker.
- daily_update: son ~40 günü çekip upsert eder (zamanlanmış görev).
- context: rapora eklenecek net mevduat faizi / TÜFE / beklenti / reel faiz satırları.
"""
from __future__ import annotations

import logging

from . import db, util
from .sources import evds

log = logging.getLogger("evds_job")


def _series_map(cfg: dict) -> dict:
    return cfg["sources"]["evds"]["series"]


def _upsert(con, code: str, rows: list[dict]) -> int:
    n = 0
    for r in rows:
        if r["value"] is None or not r["date"]:
            continue
        con.execute(
            "INSERT OR REPLACE INTO evds_daily(date,series_code,value) VALUES(?,?,?)",
            (r["date"], code, r["value"]),
        )
        n += 1
    return n


def backfill(cfg: dict) -> dict:
    """Yıl yıl çekerek EVDS'nin ~1000 satır/istek sınırını aşar (günlük seriler için kritik)."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not evds.available():
        log.warning("EVDS_API_KEY yok — backfill atlandı")
        return {}
    from datetime import date
    con = db.connect(cfg)
    smap = _series_map(cfg)
    start_year = int(cfg["sources"]["evds"]["start_date"].split("-")[-1])
    this_year = date.today().year
    counts = {}
    for logical in cfg["sources"]["evds"].get("backfill", []):
        code = smap.get(logical)
        if not code:
            continue
        total = 0
        for yr in range(start_year, this_year + 1):
            rows = evds.fetch_series(cfg, code,
                                     start=f"01-01-{yr}", end=f"31-12-{yr}")
            total += _upsert(con, code, rows)
        counts[f"{logical} ({code})"] = total
        log.info("backfill %s (%s): %d satır", logical, code, total)
    con.commit()
    con.close()
    return counts


def daily_update(cfg: dict) -> dict:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not evds.available():
        log.warning("EVDS_API_KEY yok — günlük EVDS atlandı")
        return {}
    from datetime import date, timedelta
    con = db.connect(cfg)
    smap = _series_map(cfg)
    start = (date.today() - timedelta(days=45)).strftime("%d-%m-%Y")
    counts = {}
    for logical, code in smap.items():
        rows = evds.fetch_series(cfg, code, start=start)
        counts[logical] = _upsert(con, code, rows)
    con.commit()
    con.close()
    log.info("EVDS günlük güncelleme: %s", counts)
    return counts


def _latest(con, code: str):
    """En yeni değer (tarihe göre; tarihler ISO YYYY-MM-DD, sıralanabilir)."""
    row = con.execute(
        "SELECT date,value FROM evds_daily WHERE series_code=? AND value IS NOT NULL "
        "ORDER BY date DESC LIMIT 1", (code,)
    ).fetchone()
    return (row["date"], row["value"]) if row else (None, None)


def _tufe_yoy(con, code: str):
    """Aylık TÜFE endeksinden yıllık değişim (son / 13 önceki - 1)."""
    rows = con.execute(
        "SELECT value FROM evds_daily WHERE series_code=? AND value IS NOT NULL "
        "ORDER BY date", (code,)
    ).fetchall()
    if len(rows) < 13:
        return None
    last = rows[-1]["value"]
    prev = rows[-13]["value"]
    if prev in (None, 0):
        return None
    return (last / prev - 1.0) * 100.0


def context(cfg: dict) -> dict:
    """Rapor için EVDS bağlamı. Veri yoksa None döner (rapor satırı gizler)."""
    con = db.connect(cfg)
    smap = _series_map(cfg)
    stopaj = cfg["sources"]["evds"].get("mevduat_stopaj_pct", 15.0)
    ctx = {}

    _, dep = _latest(con, smap.get("mevduat_1yil", ""))
    if dep is not None:
        ctx["mevduat_1yil_brut"] = dep
        ctx["mevduat_1yil_net"] = dep * (1.0 - stopaj / 100.0)

    tufe_date, _ = _latest(con, smap.get("tufe", ""))
    yoy = _tufe_yoy(con, smap.get("tufe", ""))
    if yoy is not None:
        ctx["tufe_yoy"] = yoy
        ctx["tufe_date"] = tufe_date

    _, bek = _latest(con, smap.get("enf_bek_12ay", ""))
    if bek is not None:
        ctx["enf_bek_12ay"] = bek

    _, pol = _latest(con, smap.get("aofm_politika", ""))
    if pol is not None:
        ctx["politika_faizi"] = pol

    # reel net mevduat faizi = net mevduat - beklenen enflasyon (yoksa TÜFE YoY)
    if "mevduat_1yil_net" in ctx:
        enf = ctx.get("enf_bek_12ay", ctx.get("tufe_yoy"))
        if enf is not None:
            ctx["reel_net_mevduat"] = (
                (1 + ctx["mevduat_1yil_net"] / 100) / (1 + enf / 100) - 1
            ) * 100

    con.close()
    return ctx


if __name__ == "__main__":
    import sys
    util.load_env()
    cfg = util.load_config()
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if mode == "backfill":
        print(backfill(cfg))
    elif mode == "context":
        print(context(cfg))
    else:
        print(daily_update(cfg))
