"""Günlük GERÇEK OHLC katmanı (Bölüm 6 — grafik yorumu için veri tabanı).

`history_daily` yalnız kapanış tutuyor ve `gram_teorik` türetilmiş bir fiyat; destek/direnç
ve hakiki ATR için yüksek/düşük şart. Bu modül yfinance'ten günlük O/H/L/C/V çekip
`ohlc_daily` tablosuna yazar.

Neden yalnız GC=F ve TRY=X saklanıyor (gram TL bar ÜRETİLMİYOR):
    high_gram ≠ high_ons × high_usdtry — günün en yüksek onsu ile en yüksek kuru aynı ana
    denk gelmez, çarpımları gerçekte hiç işlem görmemiş bir aralık üretir (şişmiş ATR +
    hayali fitiller). Bkz. config.yaml `chart:` başlığı.

Ağ çekicileri hata durumunda boş liste döner ve log'lar (proje konvansiyonu); saf okuyucu
`load_ohlc` yalnız DB'ye dokunur.

Kullanım:
    python -m src.ohlc_hist backfill    # tek seferlik tam geçmiş
    python -m src.ohlc_hist update      # günlük artımlı
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from . import db, util

log = logging.getLogger("ohlc_hist")


def _yf_daily_ohlc(ticker: str, start: str) -> list:
    """yfinance'ten günlük OHLC. Ağ/veri hatasında [] döner.

    Not: GC=F indeksi US/Eastern, TRY=X UTC — `strftime` borsa YEREL gününü verir
    (history.py:32 ile aynı konvansiyon). İkisinin H/L'si hiç birleştirilmediği için
    bu fark zararsız.
    """
    try:
        import yfinance as yf
        h = yf.Ticker(ticker).history(start=start, interval="1d")
        if h is None or len(h) == 0:
            log.warning("yfinance %s: veri yok", ticker)
            return []
        out = []
        for idx, row in h.iterrows():
            try:
                o, hi, lo, c = float(row["Open"]), float(row["High"]), \
                    float(row["Low"]), float(row["Close"])
            except (KeyError, TypeError, ValueError):
                continue
            if not all(x == x for x in (o, hi, lo, c)):     # NaN elemesi
                continue
            try:
                v = float(row.get("Volume", 0) or 0)
            except (TypeError, ValueError):
                v = 0.0
            out.append({"date": idx.strftime("%Y-%m-%d"),
                        "o": o, "h": hi, "l": lo, "c": c, "v": v})
        return out
    except Exception as e:
        log.warning("yfinance %s hata: %s", ticker, e)
        return []


def _upsert(con, symbol: str, rows: list) -> int:
    for r in rows:
        con.execute(
            "INSERT OR REPLACE INTO ohlc_daily(date,symbol,o,h,l,c,v,source) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (r["date"], symbol, r["o"], r["h"], r["l"], r["c"], r["v"], "yfinance"))
    con.commit()
    return len(rows)


def _symbols(cfg: dict) -> list:
    s = cfg["chart"]["ohlc"]["symbols"]
    return [s["ons"], s["kur"]]


def build_ohlc_daily(cfg: dict, start: Optional[str] = None) -> dict:
    """Tam geçmiş backfill (idempotent — INSERT OR REPLACE)."""
    start = start or cfg["chart"]["ohlc"]["start"]
    con = db.connect(cfg)
    out = {}
    try:
        for sym in _symbols(cfg):
            rows = _yf_daily_ohlc(sym, start)
            out[sym] = _upsert(con, sym, rows)
            log.info("ohlc backfill %s: %d bar", sym, out[sym])
    finally:
        con.close()
    return {"start": start, "yazilan": out}


def update_ohlc_daily(cfg: dict, lookback_days: Optional[int] = None) -> dict:
    """Günlük artımlı güncelleme.

    Son N günü yeniden çeker ve üzerine yazar: yfinance yakın barları revize eder ve
    bugünün barı yarımdır, dolayısıyla yeniden çekmek tabloyu kendi kendini onarır kılar.
    """
    from datetime import timedelta
    n = int(lookback_days or cfg["chart"]["ohlc"].get("guncelleme_lookback_gun", 10))
    start = (util.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")
    con = db.connect(cfg)
    out = {}
    try:
        for sym in _symbols(cfg):
            rows = _yf_daily_ohlc(sym, start)
            out[sym] = _upsert(con, sym, rows)
    finally:
        con.close()
    return {"start": start, "yazilan": out}


def load_ohlc(con, symbol: str, start: Optional[str] = None) -> list:
    """SAF okuyucu — tarih sıralı bar listesi. chart.py'nin tek DB dokunuşu."""
    if start:
        rows = con.execute(
            "SELECT date,o,h,l,c,v FROM ohlc_daily WHERE symbol=? AND date>=? ORDER BY date",
            (symbol, start)).fetchall()
    else:
        rows = con.execute(
            "SELECT date,o,h,l,c,v FROM ohlc_daily WHERE symbol=? ORDER BY date",
            (symbol,)).fetchall()
    return [{"date": r["date"], "o": r["o"], "h": r["h"],
             "l": r["l"], "c": r["c"], "v": r["v"]} for r in rows]


def drop_unclosed_bar(bars: list, today_iso: str) -> list:
    """Bugünün (henüz kapanmamış) barını atar.

    daily.yml 15:35 UTC'de koşuyor, CME altın ~21:00 UTC'de kapanıyor → her çalışma
    yarım bar görür. Saf fonksiyon: test edilebilir olsun diye tarih dışarıdan verilir.
    """
    if not bars:
        return bars
    return [b for b in bars if b["date"] < today_iso]


if __name__ == "__main__":
    util.load_env()
    cfg = util.load_config()
    from . import logging_setup
    logging_setup.setup("ohlc_hist", cfg)
    mode = sys.argv[1] if len(sys.argv) > 1 else "update"
    if mode == "backfill":
        print(build_ohlc_daily(cfg))
    else:
        print(update_ohlc_daily(cfg))
