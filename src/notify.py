"""Bölüm 1 — Bildirim motoru (Actions 15 dk workflow'una entegre).

Rehber 6.2 eşik tablosu + bildirim yorgunluğu (24s soğuma + günlük tavan) + piyasa
durum makinesi saygısı (üç bacak FRESH değilse anomali bildirimi bastırılır).

Saf çekirdek (evaluate_thresholds, apply_cooldown) birim testlidir. Durum Actions
stateless olduğundan repoda data/alert_state.json'da tutulur ve workflow commit'ler.
"""
from __future__ import annotations

import json
import logging
import math
import statistics
from datetime import datetime, timedelta, timezone

from . import calc, db, util

log = logging.getLogger("notify")


# ---------- SAF ÇEKİRDEK (testli) ----------
def evaluate_thresholds(ctx: dict, cfg: dict) -> list[dict]:
    """Eşikleri değerlendirir. ctx alanları None ise o kural pas geçilir.

    all_fresh False (hafta sonu/tatil) → anomali kuralları BASTIRILIR (indicative).
    """
    a = cfg["alerts"]
    out = []
    all_fresh = ctx.get("all_fresh", True)

    def add(tip, kural, deger, gerekce, gecersizlik):
        out.append({"tip": tip, "kural": kural, "deger": deger,
                    "gerekce": gerekce, "gecersizlik": gecersizlik})

    # Anomali kuralları yalnız üç bacak FRESH iken
    if all_fresh:
        prim = ctx.get("prim")
        primz = ctx.get("prim_z")
        if prim is not None and abs(prim) > a["prim_abs_pct"]:
            add("prim_sapma", f"|prim| > %{a['prim_abs_pct']}", prim,
                f"Prim %{prim:+.2f} teorik değerden saptı.",
                "Prim bandına dönerse (|%|<1.5) geçersiz.")
        if primz is not None and abs(primz) > a["prim_z"]:
            add("prim_z", f"|z| > {a['prim_z']}", primz,
                f"Prim z-skoru {primz:+.2f} (tarihsel aşırılık).",
                "z ortalamaya dönerse (|z|<1) geçersiz.")
        sp, p90 = ctx.get("spread"), ctx.get("spread_p90")
        if sp is not None and p90 is not None and sp > p90:
            add("makas", f"makas > p{a['spread_percentile']}", sp,
                f"Makas %{sp:.3f} tarihsel p{a['spread_percentile']} (%{p90:.3f}) üstünde — talep/panik.",
                "Makas normale dönerse geçersiz.")
        move, atr = ctx.get("daily_move"), ctx.get("atr")
        if move is not None and atr and move > a["daily_move_atr"] * atr:
            add("gunluk_hareket", f"hareket > {a['daily_move_atr']}×ATR", move,
                f"Günlük hareket {move:.0f}₺ > {a['daily_move_atr']}×ATR({atr:.0f}).",
                "Volatilite normalleşirse geçersiz.")
        qz = ctx.get("quarter_z")
        if qz is not None and abs(qz) > a["quarter_z"]:
            add("ceyrek_prim", f"çeyrek |z| > {a['quarter_z']}", qz,
                f"Çeyrek primi z {qz:+.2f} — fiziki alımda gram/çeyrek tercihi değişebilir.",
                "Çeyrek primi normale dönerse geçersiz.")
    return out


def apply_cooldown(alerts: list[dict], state: dict, now_iso: str,
                   cooldown_hours: float, daily_cap: int) -> tuple[list[dict], dict]:
    """Soğuma (aynı tip 24s) + günlük tavan. (gonderilecek, yeni_state) döner."""
    now = datetime.fromisoformat(now_iso)
    last = dict(state.get("last_sent", {}))
    today = now.date().isoformat()
    daily = dict(state.get("daily", {}))
    count = daily.get(today, 0)
    to_send = []
    for al in alerts:
        if count >= daily_cap:
            break
        prev = last.get(al["tip"])
        if prev:
            age_h = (now - datetime.fromisoformat(prev)).total_seconds() / 3600
            if age_h < cooldown_hours:
                continue                      # soğumada
        to_send.append(al)
        last[al["tip"]] = now_iso
        count += 1
    daily = {today: count}                    # sadece bugünü tut
    return to_send, {"last_sent": last, "daily": daily}


# ---------- IO / bağlam ----------
def _load_state(cfg) -> dict:
    return util.read_json(cfg["alerts"]["state_file"], {"last_sent": {}, "daily": {}})


def _save_state(cfg, state) -> None:
    util.write_json(cfg["alerts"]["state_file"], state)


def _atr_from_history(con, window=14):
    rows = con.execute(
        "SELECT gram_teorik FROM history_daily ORDER BY date DESC LIMIT ?", (window + 1,)
    ).fetchall()
    prices = [r["gram_teorik"] for r in reversed(rows)]
    if len(prices) < window + 1:
        return None
    trs = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    return sum(trs) / len(trs)


def _latest_csv_row(cfg):
    """En yeni arşiv CSV satırını okur (Actions'ta taze veri DB'den değil buradadır)."""
    import csv
    import glob
    files = sorted(glob.glob(str(util.abspath("data/archive") / "*.csv")))
    if not files:
        return None
    rows = list(csv.DictReader(open(files[-1], encoding="utf-8")))
    return rows[-1] if rows else None


def _ctx_from_csv(cfg, con, row) -> dict:
    """Taze CSV satırından güncel prim/makas/çeyrek; tarihsel bağlam DB'den."""
    from .market_calendar import MarketCalendar
    inst = cfg["instruments"]
    def f(k):
        v = row.get(k)
        try:
            return float(v) if v not in (None, "", "None") else None
        except ValueError:
            return None
    ons, usd, gram_has = f("ons_usd"), f("usdtry"), f("gram_has_sell")
    if not (ons and usd and gram_has):
        return None
    theo = calc.theoretical_gram(ons, usd, inst["troy_ounce_gram"])
    prim = calc.prim_pct(gram_has, theo)
    gh_b = f("gram_has_buy")
    spread = calc.spread_pct(gh_b, gram_has) if gh_b else None
    ts = datetime.fromisoformat(row["ts_utc"]).astimezone(timezone.utc)
    cal = MarketCalendar(cfg)
    all_fresh = not (cal.is_weekend_closed_forex(ts) or cal.is_us_gold_holiday(ts))
    return {"ons": ons, "usd": usd, "gram_has": gram_has, "theoretical": theo,
            "prim": prim, "spread": spread, "all_fresh": all_fresh, "ts": ts}


def build_context(cfg: dict) -> dict:
    """Güncel değerler taze CSV'den (varsa), tarihsel bağlam commit'li DB'den."""
    con = db.connect(cfg)
    csv_row = _latest_csv_row(cfg)
    fresh = _ctx_from_csv(cfg, con, csv_row) if csv_row else None
    latest = db.latest_prim(con)
    if fresh is None and latest is None:
        con.close()
        return {"all_fresh": False}
    # güncel değerler: taze CSV öncelikli, yoksa DB
    cur_prim = fresh["prim"] if fresh else latest["prim_pct"]
    cur_spread = fresh["spread"] if fresh else latest["spread_pct"]
    cur_theo = fresh["theoretical"] if fresh else latest["theoretical"]
    all_fresh = fresh["all_fresh"] if fresh else (not bool(latest["indicative"]))
    zmin = cfg["stats"]["zscore_min_samples"]
    n_days = db.count_valid_prim_days(con)
    prim_z = None
    if n_days >= zmin and cur_prim is not None:
        series = db.prim_series(con, only_valid=True)
        z = calc.zscore(series, cur_prim, zmin)     # güncel primin arşive karşı z'si
        prim_z = z.value
    # makas p90
    spreads = [r[0] for r in con.execute(
        "SELECT spread_pct FROM prim_history WHERE spread_pct IS NOT NULL").fetchall()]
    p = cfg["alerts"]["spread_percentile"]
    spread_p90 = None
    if len(spreads) >= 20:
        spreads.sort()
        idx = int(p / 100 * (len(spreads) - 1))
        spread_p90 = spreads[idx]
    # günlük hareket: güncel teorik vs dünkü kapanış
    atr = _atr_from_history(con)
    yrow = con.execute("SELECT gram_teorik FROM history_daily ORDER BY date DESC LIMIT 1").fetchone()
    daily_move = abs(cur_theo - yrow["gram_teorik"]) if (yrow and cur_theo) else None
    con.close()
    return {
        "all_fresh": all_fresh,
        "prim": cur_prim, "prim_z": prim_z,
        "spread": cur_spread, "spread_p90": spread_p90,
        "daily_move": daily_move, "atr": atr,
        "quarter_z": None,                    # sezon-düzeltmeli z: arşiv büyüyünce (şimdilik pas)
    }


def _format_alert(al: dict) -> str:
    return (f"🔔 <b>{al['kural']}</b>\n"
            f"{al['gerekce']}\n"
            f"<i>Geçersizlik: {al['gecersizlik']}</i>\n"
            f"— Genel bilgilendirme, yatırım tavsiyesi değildir.")


def run(cfg: dict, test_mode: bool = False) -> dict:
    from . import logging_setup
    logging_setup.setup("notify", cfg)
    from .telegram_bot import send_message
    now_iso = util.utcnow().isoformat()

    if test_mode:
        msg = ("🧪 <b>Test bildirimi</b>\nBildirim motoru canlı ve Telegram'a "
               "ulaşabiliyor. Gerçek eşiklerden bağımsız tek seferlik test.\n"
               "<i>Geçersizlik: yok (test).</i>")
        send_message(cfg, msg, parse_mode="HTML")
        return {"test": True, "gonderildi": 1}

    ctx = build_context(cfg)
    state = _load_state(cfg)
    a = cfg["alerts"]

    # Hafta sonu/tatil: anomali bastırılır; yalnız "pazartesi beklentisi" (günde 1)
    if not ctx.get("all_fresh", True):
        weekend_alert = []
        if ctx.get("prim") is not None:
            weekend_alert = [{
                "tip": "weekend_expectation",
                "kural": "Hafta sonu — pazartesi beklentisi",
                "deger": ctx["prim"],
                "gerekce": (f"Forex kapalı; Kapalıçarşı gramı donmuş teoriğe göre "
                            f"%{ctx['prim']:+.2f} sapmada — piyasanın pazartesi için "
                            f"fiyatladığı hareket."),
                "gecersizlik": "Pazartesi açılışta ons/kur güncellenince yeniden hesaplanır.",
            }]
        to_send, new_state = apply_cooldown(weekend_alert, state, now_iso,
                                            a["cooldown_hours"], 1)
        for al in to_send:
            send_message(cfg, _format_alert(al), parse_mode="HTML")
        _save_state(cfg, new_state)
        log.info("hafta sonu: %d beklenti mesajı", len(to_send))
        return {"weekend": True, "gonderildi": len(to_send)}

    alerts = evaluate_thresholds(ctx, cfg)
    to_send, new_state = apply_cooldown(alerts, state, now_iso,
                                        a["cooldown_hours"], a["daily_cap"])
    for al in to_send:
        send_message(cfg, _format_alert(al), parse_mode="HTML")
    _save_state(cfg, new_state)
    log.info("bildirim: %d tetik, %d gönderildi (soğuma/tavan sonrası)",
             len(alerts), len(to_send))
    return {"tetik": len(alerts), "gonderildi": len(to_send),
            "tipler": [x["tip"] for x in to_send]}


if __name__ == "__main__":
    import sys
    util.load_env()
    cfg = util.load_config()
    print(run(cfg, test_mode=("test" in sys.argv)))
