"""Bölüm 3 — Sinyal motoru (on-demand; 7/24 gerektirmez).

Her sinyal PROJE-REHBERI 6.3 şemasıyla: gerekçe + güven + geçersizlik koşulu.
Backtest köprüsü: tarihsel karşılığı varsa istatistik iliştirir, yoksa açıkça belirtir.
Bildirim eşik değerlendirmesi (6.2) kod olarak hazır; zamanlayıcı Oracle'a bırakılmıştır.
"""
from __future__ import annotations

import logging
import math
import statistics
from typing import Optional

from . import calc, db, util

log = logging.getLogger("signals")

UYARI = "Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir."


def _signal(sinyal, yon, profil, gerekce, guven, gecersizlik, ufuk, backtest=None):
    return {
        "sinyal": sinyal, "yon": yon, "profil": profil,
        "gerekce": gerekce, "guven": guven, "gecersizlik": gecersizlik,
        "ufuk": ufuk, "backtest": backtest or "tarihsel doğrulaması yok",
        "uyari": UYARI,
    }


def atr_proxy(prices: list[float], window: int = 14) -> Optional[float]:
    """Kapanış-kapanış ATR proxy'si (günlük |Δ| ortalaması). Gerçek HL yok."""
    if len(prices) < window + 1:
        return None
    trs = [abs(prices[i] - prices[i - 1]) for i in range(len(prices) - window, len(prices))]
    return sum(trs) / len(trs)


def _history(con):
    return con.execute(
        "SELECT date,ons_usd,usdtry,gram_teorik FROM history_daily ORDER BY date"
    ).fetchall()


def _current_regime(cfg, con):
    """Bugünkü rejim etiketi + backtest'ten o rejimin 3 ay ileri getirisi."""
    from . import backtest as bt
    hist = [dict(r) for r in _history(con)]
    if len(hist) < cfg["backtest"]["gma_window"] + 10:
        return None, None
    try:
        dfii = bt._fred_aligned(cfg, [h["date"] for h in hist])
        labels = bt._label_regimes(cfg, hist, dfii)
    except Exception as e:
        log.warning("rejim hesabı hata: %s", e)
        return None, None
    cur = labels[-1]
    stats = bt._regime_stats_table(hist, labels, cfg["backtest"]["horizons_days"]["3ay"])
    return cur, stats.get(cur, {}).get("gram_tl")


def build_signals(cfg: dict) -> dict:
    from . import logging_setup
    logging_setup.setup("signals", cfg)
    con = db.connect(cfg)
    out = []

    latest = db.latest_prim(con)
    zmin = cfg["stats"]["zscore_min_samples"]

    # 1) Prim z-skoru (canlı arşiv) ----------------------------------------
    n_valid = db.count_valid_prim(con)
    if latest is None:
        out.append(_signal("prim_zskoru", "veri_bekliyor", ["birikimci"],
                           ["Henüz prim verisi yok."], "yok",
                           "Toplayıcı çalışıp arşiv birikince geçerli olur.", "—"))
    elif n_valid < zmin:
        out.append(_signal("prim_zskoru", "veri_bekliyor", ["birikimci", "makasçı"],
                           [f"Canlı prim arşivi yetersiz ({n_valid}/{zmin} geçerli kayıt).",
                            f"Güncel prim {latest['prim_pct']:+.2f}% ama z-skor için tarihçe eksik."],
                           "yok",
                           "Arşiv 60+ geçerli kayda ulaşınca z-skor sinyali devreye girer.", "—"))
    else:
        series = db.prim_series(con, only_valid=True)
        z = calc.zscore(series[:-1], series[-1], zmin)
        yon = ("alim_lehine" if (z.value or 0) < -1 else
               "temkinli" if (z.value or 0) > 2 else "notr")
        out.append(_signal("prim_zskoru", yon, ["birikimci", "makasçı"],
                           [f"Prim {latest['prim_pct']:+.2f}%, z={z.value:+.2f} (n={z.n}).",
                            "z<-1 birikim penceresi, z>+2 pahalı."],
                           "orta" if abs(z.value or 0) > 1 else "düşük",
                           "Prim ortalamaya dönerse (|z|<0.5) sinyal nötrlenir.", "1-4 hafta"))

    # 2) Kadran uzlaşısı ----------------------------------------------------
    try:
        from . import indicators
        from .evds_job import context as evds_context
        ctx = evds_context(cfg)
        panel = indicators.build_panel(cfg, ctx.get("reel_net_mevduat"))
        c = panel["consensus"]
        yon = ("olumlu" if c["yon"] == "olumlu" else
               "olumsuz" if c["yon"] == "olumsuz" else "notr")
        ger = [f"{s.name}: {s.label}" for s in panel["signals"] if s.score is not None]
        out.append(_signal("kadran_uzlasisi", yon, ["trend"],
                           ger + [f"Uzlaşı skoru {c['score']:+d}/{c['n']}."],
                           "orta" if abs(c["normalized"]) > 0.5 else "düşük",
                           "Göstergelerden biri yön değiştirirse uzlaşı bozulur.", "1-3 ay"))
    except Exception as e:
        log.warning("kadran sinyali hata: %s", e)

    # 3) Güncel rejim + backtest köprüsü -----------------------------------
    regime, rstat = _current_regime(cfg, con)
    if regime:
        bridge = "tarihsel doğrulaması yok"
        if rstat and rstat.get("n"):
            weak = " (istatistiksel olarak zayıf)" if rstat.get("weak") else ""
            bridge = (f"Bu rejim 2016'dan beri {rstat['n']} gün; 3 ay sonra gram TL "
                      f"medyan {rstat['medyan']:+.1f}%, kazanma %{rstat['kazanma_pct']:.0f}{weak}.")
        defs = {"A": "birikim penceresi", "B": "güçlü trend", "C": "zayıf rejim",
                "D": "anomali/MB alım rejimi", "X": "karışık"}
        out.append(_signal("rejim", defs.get(regime, regime), ["trend", "birikimci"],
                           [f"Güncel rejim: {regime} ({defs.get(regime,'')}).",
                            "Rejim = ons 200GMA × reel faiz trendi × kur oynaklığı."],
                           "orta",
                           "Ons 200GMA'yı veya reel faiz trendini kırarsa rejim değişir.",
                           "1-3 ay", backtest=bridge))

    # 4) ATR kademe önerisi -------------------------------------------------
    hist = _history(con)
    prices = [h["gram_teorik"] for h in hist]
    atr = atr_proxy(prices)
    spot = latest["market_has"] if latest else (prices[-1] if prices else None)
    if atr and spot:
        k1, k2 = spot - 1.5 * atr, spot - 3.0 * atr
        out.append(_signal("atr_kademe", "kademeli_alim", ["birikimci", "trend"],
                           [f"Spot ~{spot:.0f}₺, ATR(14)~{atr:.0f}₺.",
                            f"Kademeler: {spot:.0f} / {k1:.0f} / {k2:.0f}."],
                           "orta",
                           "Volatilite rejimi değişirse (ATR sıçraması) kademeler yeniden hesaplanır.",
                           "değişken",
                           backtest="ATR kademe mekanik kural; yönsel getiri iddiası yok."))

    # 5) Çeyrek prim durumu -------------------------------------------------
    if latest and latest["quarter_prim_pct"] is not None:
        qp = latest["quarter_prim_pct"]
        yon = "gram_tercih" if qp > 1.0 else "notr"
        out.append(_signal("ceyrek_prim", yon, ["birikimci"],
                           [f"Çeyrek primi {qp:+.2f}%.",
                            "Yüksek çeyrek primi → fiziki alımda gram/külçe avantajlı."],
                           "düşük",
                           "Çeyrek primi normale dönerse fark kapanır.", "sezonluk"))

    con.close()
    return {"n": len(out), "signals": out}


# ---------- Bildirim eşik değerlendirmesi (rehber 6.2) — kod hazır, zamanlayıcı Oracle'da ----------
def evaluate_alerts(cfg: dict) -> list[dict]:
    con = db.connect(cfg)
    latest = db.latest_prim(con)
    alerts = []
    if latest is None:
        con.close()
        return alerts
    th = cfg.get("alerts", {})
    prim_abs = th.get("prim_abs_pct", 1.5)
    z_thr = th.get("prim_z", 2.0)
    atr_mult = th.get("daily_move_atr", 2.0)

    if latest["prim_pct"] is not None and abs(latest["prim_pct"]) > prim_abs:
        alerts.append({"tip": "prim_sapma", "deger": latest["prim_pct"],
                       "mesaj": f"Prim %{latest['prim_pct']:+.2f} (|>{prim_abs}|)"})
    n_valid = db.count_valid_prim(con)
    if n_valid >= cfg["stats"]["zscore_min_samples"]:
        series = db.prim_series(con, only_valid=True)
        z = calc.zscore(series[:-1], series[-1], cfg["stats"]["zscore_min_samples"])
        if z.value is not None and abs(z.value) > z_thr:
            alerts.append({"tip": "prim_z", "deger": z.value,
                           "mesaj": f"Prim z={z.value:+.2f} (|>{z_thr}|)"})
    # günlük hareket > N×ATR (history_daily'den)
    hist = con.execute(
        "SELECT gram_teorik FROM history_daily ORDER BY date DESC LIMIT 20").fetchall()
    prices = [r["gram_teorik"] for r in reversed(hist)]
    atr = atr_proxy(prices)
    if atr and len(prices) >= 2:
        move = abs(prices[-1] - prices[-2])
        if move > atr_mult * atr:
            alerts.append({"tip": "gunluk_hareket", "deger": move,
                           "mesaj": f"Günlük hareket {move:.0f}₺ > {atr_mult}×ATR"})
    con.close()
    return alerts


def format_signals_md(result: dict) -> str:
    L = ["## Sinyaller", ""]
    if not result["signals"]:
        return "## Sinyaller\n\n_Sinyal üretilemedi._"
    for s in result["signals"]:
        L.append(f"### {s['sinyal']} → **{s['yon']}**  ·  güven: {s['guven']}")
        L.append(f"- Profil: {', '.join(s['profil'])} · Ufuk: {s['ufuk']}")
        for g in s["gerekce"]:
            L.append(f"- {g}")
        L.append(f"- 📊 Backtest: {s['backtest']}")
        L.append(f"- ❌ Geçersizlik: {s['gecersizlik']}")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    import json
    import sys
    util.load_env()
    cfg = util.load_config()
    if len(sys.argv) > 1 and sys.argv[1] == "alerts":
        print(json.dumps(evaluate_alerts(cfg), ensure_ascii=False, indent=2))
    else:
        r = build_signals(cfg)
        print(json.dumps(r, ensure_ascii=False, indent=2))
