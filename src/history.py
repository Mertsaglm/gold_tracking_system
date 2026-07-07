"""Bölüm 1 — Tarihsel günlük veri katmanı (backtest'in temeli).

- build_history_daily: yfinance günlük ons (2016+) × EVDS günlük USD → teorik has gram TL.
- monthly_prim_proxy: aylık külçe (TP.MK.KUL.YTL) / aylık teorik − 1; saflık bazı tespiti.
- data_quality: eksik gün, aykırı değer (>Nσ), kaynak tutarlılık örneklemi.
"""
from __future__ import annotations

import logging
import statistics

from . import calc, db, util

log = logging.getLogger("history")


def _yf_ons_daily(cfg: dict, start: str):
    """yfinance günlük ons kapanışı. Birincil XAUUSD=X, fallback GC=F. {date:price}, source."""
    import yfinance as yf
    for tk in (cfg["sources"]["yfinance"].get("ons_hist_primary", "XAUUSD=X"),
               cfg["sources"]["yfinance"]["ons_ticker"]):
        try:
            h = yf.Ticker(tk).history(start=start, interval="1d")
            close = h["Close"].dropna()
            if len(close) >= 200:
                out = {}
                for ts, v in close.items():
                    out[ts.strftime("%Y-%m-%d")] = float(v)
                return out, tk
        except Exception as e:
            log.warning("yf hist %s hata: %s", tk, e)
    return {}, None


def _evds_usd_map(con, code: str) -> dict:
    rows = con.execute(
        "SELECT date,value FROM evds_daily WHERE series_code=? AND value IS NOT NULL",
        (code,),
    ).fetchall()
    return {r["date"]: r["value"] for r in rows}


def build_history_daily(cfg: dict, start: str = "2016-01-01") -> dict:
    from . import logging_setup
    logging_setup.setup("history", cfg)
    con = db.connect(cfg)
    troy = cfg["instruments"]["troy_ounce_gram"]
    usd_code = cfg["sources"]["evds"]["series"]["usdtry_sell"]

    ons_map, source = _yf_ons_daily(cfg, start)
    usd_map = _evds_usd_map(con, usd_code)
    if not ons_map or not usd_map:
        log.warning("history: ons(%d) veya usd(%d) eksik", len(ons_map), len(usd_map))
        con.close()
        return {"rows": 0}

    # ortak günlerde birleştir (EVDS iş günü; yfinance kendi takvimi)
    common = sorted(set(ons_map) & set(usd_map))
    n = 0
    for d in common:
        ons, usd = ons_map[d], usd_map[d]
        gram = calc.theoretical_gram(ons, usd, troy)
        con.execute(
            "INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,gram_teorik,ons_source)"
            " VALUES(?,?,?,?,?)", (d, ons, usd, gram, source),
        )
        n += 1
    con.commit()
    rng = (common[0], common[-1]) if common else (None, None)
    log.info("history_daily: %d gün (%s..%s), ons kaynak=%s", n, rng[0], rng[1], source)
    con.close()
    return {"rows": n, "start": rng[0], "end": rng[1], "ons_source": source,
            "ons_days": len(ons_map), "usd_days": len(usd_map)}


def _monthly_avg_theoretical(con) -> dict:
    """history_daily'den ay-başı ISO anahtarlı aylık ortalama teorik gram."""
    rows = con.execute(
        "SELECT substr(date,1,7) ym, AVG(gram_teorik) g FROM history_daily GROUP BY ym"
    ).fetchall()
    return {f"{r['ym']}-01": r["g"] for r in rows}


def monthly_prim_proxy(cfg: dict) -> dict:
    """Aylık külçe (TP.MK.KUL.YTL) / aylık teorik gram − 1. Saflık bazını tespit eder."""
    con = db.connect(cfg)
    kod = cfg["sources"]["evds"]["series"]["kulce_altin_sell"]
    kulce = {r["date"]: r["value"] for r in con.execute(
        "SELECT date,value FROM evds_daily WHERE series_code=? AND value IS NOT NULL", (kod,))}
    theo = _monthly_avg_theoretical(con)
    con.close()

    common = sorted(set(kulce) & set(theo))
    if not common:
        return {"error": "ortak ay yok"}
    # Saflık tespiti: külçe/teorik oranının medyanı ~1.00 (has/1000) mü, ~0.995 (995) mü?
    ratios = [kulce[d] / theo[d] for d in common if theo[d]]
    med = statistics.median(ratios)
    if med > 0.999:
        purity, basis = 1.0, "has (1000/1000) — külçe teorik ile ~birebir"
    elif abs(med - 0.995) < abs(med - 1.0):
        purity, basis = 0.995, "995/1000 — külçe teoriğin ~%0.5 altında"
    else:
        purity, basis = med, f"ampirik oran medyanı {med:.4f}"

    series = []
    for d in common:
        # teoriği külçe saflık bazına indir, sonra prim
        theo_adj = theo[d] * purity
        prim = (kulce[d] / theo_adj - 1.0) * 100.0
        series.append({"date": d, "kulce": kulce[d], "teorik": theo[d], "prim_pct": prim})
    return {"n": len(series), "purity": purity, "basis": basis,
            "ratio_median": med, "series": series}


def data_quality(cfg: dict, sigma: float = 6.0) -> dict:
    """Eksik gün, aykırı değer (>Nσ günlük değişim), yfinance vs EVDS kur tutarlılığı."""
    con = db.connect(cfg)
    rows = con.execute(
        "SELECT date,ons_usd,usdtry,gram_teorik FROM history_daily ORDER BY date"
    ).fetchall()
    if len(rows) < 30:
        con.close()
        return {"error": "yetersiz veri"}

    # günlük log-getiri + aykırı tarama (gram teorik)
    import math
    rets, outliers = [], []
    for i in range(1, len(rows)):
        p0, p1 = rows[i - 1]["gram_teorik"], rows[i]["gram_teorik"]
        if p0 and p1:
            rets.append((rows[i]["date"], math.log(p1 / p0)))
    mu = statistics.mean(r for _, r in rets)
    sd = statistics.pstdev(r for _, r in rets)
    for d, r in rets:
        if sd and abs(r - mu) > sigma * sd:
            outliers.append({"date": d, "gunluk_pct": (math.exp(r) - 1) * 100, "z": (r - mu) / sd})

    # eksik iş günü: ardışık takvim günlerinde >4 gün boşluk (uzun tatil/kesinti)
    from datetime import date
    gaps = []
    ds = [date.fromisoformat(r["date"]) for r in rows]
    for i in range(1, len(ds)):
        delta = (ds[i] - ds[i - 1]).days
        if delta > 5:
            gaps.append({"from": ds[i - 1].isoformat(), "to": ds[i].isoformat(), "gun": delta})

    con.close()
    return {
        "gun_sayisi": len(rows), "aralik": (rows[0]["date"], rows[-1]["date"]),
        "gunluk_vol_pct": sd * 100, "aykiri_sayisi": len(outliers),
        "aykirilar": outliers[:10], "buyuk_bosluklar": gaps[:10],
    }


if __name__ == "__main__":
    import sys
    util.load_env()
    cfg = util.load_config()
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    if mode == "build":
        print(build_history_daily(cfg))
    elif mode == "prim":
        r = monthly_prim_proxy(cfg)
        print({k: v for k, v in r.items() if k != "series"})
    elif mode == "quality":
        print(data_quality(cfg))
