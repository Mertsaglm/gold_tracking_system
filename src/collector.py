"""Ana toplayıcı döngüsü: Truncgil (60sn) + yfinance (5dk) -> tick/OHLC + prim snapshot.

Kaynak düşse log + devam. Ctrl+C ile temiz kapanış.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from . import calc, db, logging_setup, util
from .market_calendar import MarketCalendar
from .sources import truncgil, yf
from .state_machine import prim_validity

log = logging.getLogger("collector")

# Son bilinen ons/kur (yfinance seyrek çekilir; ara döngülerde son değer kullanılır)
_last_ons: Optional[float] = None
_last_usdtry: Optional[float] = None
_last_yf_ts: float = 0.0


def _minute(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def _store_truncgil(con, snap: truncgil.TruncgilSnapshot, ts: datetime) -> dict:
    """Tick + OHLC yazar, satış fiyatlarını sözlük olarak döner."""
    sells = {}
    tsx = util.iso(ts)
    minute = _minute(ts)
    for sym, (buy, sell) in snap.prices.items():
        db.insert_tick(con, tsx, "truncgil", sym, buy, sell)
        if sell is not None:
            db.update_ohlc(con, minute, sym, sell)
            sells[sym] = sell
    return sells


def _refresh_yf(con, cfg, ts: datetime) -> None:
    global _last_ons, _last_usdtry, _last_yf_ts
    snap = yf.fetch(cfg)
    tsx = util.iso(ts)
    minute = _minute(ts)
    if snap.ons_usd:
        _last_ons = snap.ons_usd
        db.insert_tick(con, tsx, "yfinance", "ons_usd", None, snap.ons_usd)
        db.update_ohlc(con, minute, "ons_usd", snap.ons_usd)
    if snap.usdtry:
        _last_usdtry = snap.usdtry
        db.insert_tick(con, tsx, "yfinance", "usdtry", None, snap.usdtry)
        db.update_ohlc(con, minute, "usdtry", snap.usdtry)
    _last_yf_ts = time.time()
    log.info("yfinance: ons=%s usdtry=%s", _last_ons, _last_usdtry)


def compute_and_store_prim(con, cfg, cal: MarketCalendar,
                           sells: dict, ts: datetime) -> Optional[dict]:
    """Prim/makas/çeyrek primi/dekompozisyon snapshot'ı üretir ve yazar."""
    inst = cfg["instruments"]
    gram_has = sells.get("gram_has_altin")
    gram_retail = sells.get("gram_altin")
    ceyrek = sells.get("ceyrek")
    tc = cfg["sources"]["truncgil"]["keys"]

    if _last_ons is None or _last_usdtry is None or gram_has is None:
        log.info("prim atlandı (ons/kur/gram eksik)")
        return None

    theoretical = calc.theoretical_gram(_last_ons, _last_usdtry, inst["troy_ounce_gram"])
    prim = calc.prim_pct(gram_has, theoretical)
    # saflık düzeltmesiz (naif): perakende gramı has gibi kabul et
    prim_naive = calc.prim_pct(gram_retail, theoretical) if gram_retail else None

    # makas: has gram alış/satış
    buy_has, sell_has = None, None
    row = con.execute(
        "SELECT buying,selling FROM ticks WHERE symbol='gram_has_altin' "
        "ORDER BY ts_utc DESC LIMIT 1").fetchone()
    if row:
        buy_has, sell_has = row["buying"], row["selling"]
    spread = calc.spread_pct(buy_has, sell_has) if (buy_has and sell_has) else None

    qp = None
    if ceyrek is not None:
        c = inst["coins"]["ceyrek"]
        qp = calc.quarter_prim_pct(ceyrek, gram_has, c["gross_g"], c["milyem"])

    # durum makinesi
    last_ons_ts = db.last_tick_time(con, "ons_usd")
    last_kur_ts = db.last_tick_time(con, "usdtry")
    last_gram_ts = db.last_tick_time(con, "gram_has_altin")
    val = prim_validity(ts, last_ons_ts, last_kur_ts, last_gram_ts, cfg, cal)

    db.insert_prim(
        con,
        ts_utc=util.iso(ts), ons_usd=_last_ons, usdtry=_last_usdtry,
        theoretical=theoretical, market_has=gram_has, gram_retail=gram_retail,
        prim_pct=prim, prim_pct_naive=prim_naive, spread_pct=spread,
        quarter_prim_pct=qp,
        indicative=1 if val.indicative else 0,
        weekend=1 if val.weekend else 0,
        holiday=1 if val.holiday else 0,
        reason=val.reason,
    )

    # hafta sonu beklenti serisi (forex kapalıyken)
    if val.weekend and gram_has is not None:
        exp = calc.prim_pct(gram_has, theoretical)  # donmuş teorik ile
        db.insert_weekend_exp(con, util.iso(ts), gram_has, theoretical, exp)

    snap = {
        "prim": prim, "prim_naive": prim_naive, "spread": spread,
        "quarter_prim": qp, "theoretical": theoretical, "market_has": gram_has,
        "indicative": val.indicative, "weekend": val.weekend, "reason": val.reason,
    }
    tag = "INDICATIVE" if val.indicative else "GECERLI"
    log.info("prim=%.3f%% (naive=%s) makas=%s ceyrek_prim=%s [%s %s]",
             prim, f"{prim_naive:.3f}" if prim_naive else "—",
             f"{spread:.3f}" if spread else "—",
             f"{qp:.2f}" if qp else "—", tag, val.reason)
    return snap


def run(cfg: dict, max_seconds: Optional[float] = None) -> None:
    global log
    log = logging_setup.setup("collector", cfg)
    cal = MarketCalendar(cfg)
    con = db.connect(cfg)
    poll = cfg["sources"]["truncgil"]["poll_seconds"]
    yf_poll = cfg["sources"]["yfinance"]["poll_seconds"]
    start = time.time()
    log.info("Toplayıcı başladı. Truncgil %ss, yfinance %ss.", poll, yf_poll)

    # ilk turda yfinance'i hemen çek
    try:
        _refresh_yf(con, cfg, util.utcnow())
        con.commit()
    except Exception as e:
        log.warning("ilk yfinance hata: %s", e)

    try:
        while True:
            ts = util.utcnow()
            snap = truncgil.fetch(cfg)
            if snap.ok:
                sells = _store_truncgil(con, snap, ts)
                if time.time() - _last_yf_ts >= yf_poll:
                    _refresh_yf(con, cfg, ts)
                compute_and_store_prim(con, cfg, cal, sells, ts)
            else:
                log.warning("truncgil bu turda başarısız, atlandı")
            con.commit()

            if max_seconds is not None and time.time() - start >= max_seconds:
                log.info("max_seconds doldu, çıkılıyor.")
                break
            time.sleep(poll)
    except KeyboardInterrupt:
        log.info("Ctrl+C — temiz kapanış.")
    finally:
        con.commit()
        con.close()


if __name__ == "__main__":
    util.load_env()
    run(util.load_config())
