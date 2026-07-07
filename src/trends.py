"""Bölüm 3 — Google Trends kalabalık göstergesi (kontrarian).

"gram altın" arama ilgisinin 5 yıllık z-skoru. Yüksek ilgi (z>eşik) = kalabalık yoğun
→ kontrarian OLUMSUZ; düşük ilgi → nötr/olumlu. pytrends kırılgan; çekilemezse "veri yok"
(GLD ile aynı davranış, uzlaşı paydasından çıkar). Günlük önbellek rate-limit'e karşı.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from typing import Optional

from . import util
from .indicators import Signal, OLUMLU, NOTR, OLUMSUZ, YOK

log = logging.getLogger("trends")


# ---------- Saf etiketleme (TESTLİ) ----------
def label_trends(z: float, thr: float) -> str:
    """Kontrarian: ilgi z > thr → kalabalık yoğun (OLUMSUZ); z < -thr → düşük ilgi (OLUMLU)."""
    if z > thr:
        return OLUMSUZ
    if z < -thr:
        return OLUMLU
    return NOTR


def _load_cache(cfg) -> Optional[dict]:
    c = util.read_json(cfg["trends"]["cache_file"], None)
    if not c:
        return None
    try:
        ts = datetime.fromisoformat(c["ts"])
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_h < cfg["trends"]["cache_hours"]:
            return c
    except Exception:
        return None
    return None


def _save_cache(cfg, values: list[float], dates: list[str]) -> None:
    util.write_json(cfg["trends"]["cache_file"],
                    {"ts": datetime.now(timezone.utc).isoformat(),
                     "values": values, "dates": dates})


def fetch_interest_df(cfg: dict):
    """(dates, values) haftalık ilgi. Önbellek → pytrends. Hata: (None, None)."""
    cached = _load_cache(cfg)
    if cached and cached.get("dates"):
        return cached["dates"], cached["values"]
    tc = cfg["trends"]
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="tr-TR", tz=180)
        pt.build_payload([tc["keywords"][0]], geo=tc["geo"], timeframe=tc["timeframe"])
        df = pt.interest_over_time()
        if df is None or df.empty:
            return None, None
        vals = [float(x) for x in df[tc["keywords"][0]].tolist()]
        dates = [d.strftime("%Y-%m-%d") for d in df.index]
        _save_cache(cfg, vals, dates)
        return dates, vals
    except Exception as e:
        log.warning("pytrends hata: %s", e)
        return None, None


def fetch_interest(cfg: dict) -> Optional[list[float]]:
    _, vals = fetch_interest_df(cfg)
    return vals


def historical_validation(cfg: dict) -> dict:
    """İlgi zirvelerinin (haftalık z>eşik) sonrasındaki gram getirisi, tabana karşı.

    Bölüm 0 metodolojisi: örtüşmeyen pencere + taban farkı + zayıf-N etiketi.
    """
    import statistics as st
    from . import backtest as bt, db
    dates, vals = fetch_interest_df(cfg)
    if not dates or len(vals) < 30:
        return {"durum": "veri yok (pytrends çekilemedi)"}
    mu, sd = st.mean(vals), st.pstdev(vals)
    if sd == 0:
        return {"durum": "varyans yok"}
    thr = cfg["indicators"]["thresholds"]["trends_z"]
    peak_weeks = {dates[i] for i in range(len(vals)) if (vals[i] - mu) / sd > thr}

    con = db.connect(cfg)
    hist = [dict(r) for r in con.execute(
        "SELECT date,gram_teorik FROM history_daily ORDER BY date").fetchall()]
    con.close()
    hdates = [h["date"] for h in hist]
    gram = [h["gram_teorik"] for h in hist]
    # her zirve haftasını >= o tarihe ilk gün indeksine eşle
    peak_idx = []
    for pw in sorted(peak_weeks):
        for i, d in enumerate(hdates):
            if d >= pw:
                peak_idx.append(i)
                break
    out = {"zirve_hafta": len(peak_weeks), "eslesen": len(peak_idx)}
    for hn, hd in (("1ay", 21), ("3ay", 63)):
        sig = bt.dist_stats(bt.forward_returns_nonoverlap(hdates, gram, peak_idx, hd))
        base = bt.dist_stats(bt.forward_returns_nonoverlap(hdates, gram, list(range(len(hist))), hd))
        diff = (sig["medyan"] - base["medyan"]) if sig.get("n") and base.get("n") else None
        out[hn] = {"sinyal": sig, "taban_medyan": base.get("medyan"),
                   "fark_puan": diff, "zayif": sig.get("weak", True)}
    return out


def trends_signal(cfg: dict) -> Signal:
    vals = fetch_interest(cfg)
    if not vals or len(vals) < 20:
        return Signal("Google Trends 'gram altın'", YOK, "pytrends verisi yok")
    mu = statistics.mean(vals[:-1])
    sd = statistics.pstdev(vals[:-1])
    if sd == 0:
        return Signal("Google Trends 'gram altın'", NOTR, "varyans yok")
    z = (vals[-1] - mu) / sd
    lbl = label_trends(z, cfg["indicators"]["thresholds"]["trends_z"])
    aciklama = {"olumsuz": "kalabalık yoğun (kontrarian)", "olumlu": "düşük ilgi",
                "nötr": "normal ilgi"}.get(lbl, "")
    return Signal("Google Trends 'gram altın'", lbl, f"z={z:+.2f} · {aciklama}")


if __name__ == "__main__":
    util.load_env()
    cfg = util.load_config()
    s = trends_signal(cfg)
    print(s.name, "|", s.label, "|", s.detail)
