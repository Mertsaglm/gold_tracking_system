"""yfinance kaynağı: ons (XAU/USD) ve USD/TRY. Gecikmeli, ücretsiz.

yfinance yüklü değilse veya ağ yoksa None döner (çökme yok).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("yf")


@dataclass
class YfSnapshot:
    ons_usd: Optional[float] = None
    usdtry: Optional[float] = None
    error: Optional[str] = None


def _last_price(ticker: str) -> Optional[float]:
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        # fast_info hızlı ve az veri çeker
        fi = getattr(t, "fast_info", None)
        if fi:
            for attr in ("last_price", "lastPrice"):
                v = None
                try:
                    v = fi[attr] if isinstance(fi, dict) else getattr(fi, attr, None)
                except Exception:
                    v = None
                if v:
                    return float(v)
        # yedek: son kapanış
        hist = t.history(period="5d", interval="1h")
        if not hist.empty:
            return float(hist["Close"].dropna().iloc[-1])
    except Exception as e:
        log.warning("yf %s hata: %s", ticker, e)
    return None


def fetch(cfg: dict) -> YfSnapshot:
    yc = cfg["sources"]["yfinance"]
    try:
        ons = _last_price(yc["ons_ticker"])
        if ons is None:
            ons = _last_price(yc["ons_fallback_ticker"])
        usdtry = _last_price(yc["usdtry_ticker"])
        return YfSnapshot(ons_usd=ons, usdtry=usdtry)
    except Exception as e:
        log.warning("yf fetch hata: %s", e)
        return YfSnapshot(error=str(e))
