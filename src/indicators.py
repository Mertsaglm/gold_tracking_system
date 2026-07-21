"""Kadran / gösterge uzlaşı paneli (rapor E.2).

Etiketleme fonksiyonları saf ve testli; veri çekiciler ağ hatasında None döner
(gösterge "veri yok" olur, uzlaşı skorunun paydası dışında kalır).
"""
from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from . import util

log = logging.getLogger("indicators")

OLUMLU, NOTR, OLUMSUZ, YOK = "olumlu", "nötr", "olumsuz", "veri yok"
_SCORE = {OLUMLU: 1, NOTR: 0, OLUMSUZ: -1}


@dataclass
class Signal:
    name: str
    label: str
    detail: str

    @property
    def score(self) -> Optional[int]:
        return _SCORE.get(self.label)  # YOK -> None (paydadan çıkar)


# ---------- Saf etiketleme fonksiyonları (TESTLİ) ----------
def label_real_rate(delta_bps: float, thr_bps: float) -> str:
    """Reel faiz DÜŞÜŞÜ altın için olumlu."""
    if abs(delta_bps) < thr_bps:
        return NOTR
    return OLUMLU if delta_bps < 0 else OLUMSUZ


def label_dxy(pct_change: float, thr_pct: float) -> str:
    """Dolar endeksi DÜŞÜŞÜ altın için olumlu."""
    if abs(pct_change) < thr_pct:
        return NOTR
    return OLUMLU if pct_change < 0 else OLUMSUZ


def label_gma(price: float, gma50: float, gma200: float) -> str:
    """Fiyat > 200GMA ve 50 > 200 -> olumlu; fiyat < 200GMA ve 50 < 200 -> olumsuz."""
    if price > gma200 and gma50 >= gma200:
        return OLUMLU
    if price < gma200 and gma50 < gma200:
        return OLUMSUZ
    return NOTR


def label_gld(ton_pct_change: float, thr_pct: float) -> str:
    """SPDR GLD tonaj ARTIŞI altın için olumlu."""
    if abs(ton_pct_change) < thr_pct:
        return NOTR
    return OLUMLU if ton_pct_change > 0 else OLUMSUZ


def label_real_deposit(reel_net_pct: float, dusuk: float, yuksek: float) -> str:
    """Reel net mevduat DÜŞÜK -> altın olumlu; YÜKSEK -> olumsuz (mevduat rekabetçi)."""
    if reel_net_pct < dusuk:
        return OLUMLU
    if reel_net_pct > yuksek:
        return OLUMSUZ
    return NOTR


def consensus(signals: list[Signal]) -> dict:
    scored = [s.score for s in signals if s.score is not None]
    total = sum(scored)
    n = len(scored)
    if n == 0:
        return {"score": 0, "n": 0, "yon": NOTR, "normalized": 0.0}
    norm = total / n
    yon = OLUMLU if norm > 0.25 else OLUMSUZ if norm < -0.25 else NOTR
    return {"score": total, "n": n, "yon": yon, "normalized": norm}


# ---------- Veri çekiciler (ağ hatasında None) ----------
# Süreç içi memo. build_panel tek rapor akışında birden çok tüketici tarafından çağrılıyor
# (report.py + signals.py + aipaket.py) → aynı FRED serisi 3 kez çekiliyordu. Bu hem yavaş
# hem de Actions'ta zaman aşımı riskini 3'e katlıyordu (20 Tem 2026 log'unda görüldü).
_FRED_CACHE: dict = {}


def _fred_csv(cfg: dict, series_id: str) -> Optional[list[tuple[str, float]]]:
    """FRED CSV serisi çeker. Ağ hatasında None (gösterge 'veri yok' olur).

    Actions runner'larından fredgraph.csv 25 sn'de yetişmiyordu; timeout config'e
    taşındı ve yeniden deneme eklendi.
    """
    if series_id in _FRED_CACHE:
        return _FRED_CACHE[series_id]
    ic = cfg["indicators"]
    timeout = float(ic.get("fred_timeout_seconds", 60))
    tries = int(ic.get("fred_retry", 2)) + 1
    url = f"{ic['fred_base']}?id={series_id}"
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "altin/1.0"})
            r.raise_for_status()
            out = []
            for line in r.text.splitlines()[1:]:
                parts = line.split(",")
                if len(parts) < 2:
                    continue
                d, v = parts[0], parts[-1]
                if v in (".", "", "NaN"):
                    continue
                try:
                    out.append((d, float(v)))
                except ValueError:
                    continue
            if out:
                _FRED_CACHE[series_id] = out
                return out
            return None
        except Exception as e:
            log.warning("FRED %s hata (deneme %d/%d): %s", series_id, attempt, tries, e)
            if attempt < tries:
                time.sleep(2.0 * attempt)          # basit geri çekilme
    return None


def _trend_delta(series: list[tuple[str, float]], lookback: int):
    """Son değer − 'lookback' gözlem öncesi. (latest, prev, delta) döner."""
    vals = [v for _, v in series]
    if len(vals) < 2:
        return None
    latest = vals[-1]
    idx = max(0, len(vals) - 1 - lookback)
    prev = vals[idx]
    return latest, prev, latest - prev


def real_rate_signal(cfg: dict) -> Signal:
    ic = cfg["indicators"]
    s = _fred_csv(cfg, ic["real_rate_series"])
    td = _trend_delta(s, ic["trend_lookback_days"]) if s else None
    if not td:
        return Signal("ABD 10Y reel faiz", YOK, "FRED verisi yok")
    latest, prev, delta = td
    delta_bps = delta * 100.0  # yüzde puanı -> bps
    lbl = label_real_rate(delta_bps, ic["thresholds"]["real_rate_bps"])
    return Signal("ABD 10Y reel faiz", lbl,
                  f"{prev:.2f}% → {latest:.2f}% ({delta_bps:+.0f}bps/~1ay)")


def dxy_signal(cfg: dict) -> Signal:
    ic = cfg["indicators"]
    s = _fred_csv(cfg, ic["dxy_series"])
    td = _trend_delta(s, ic["trend_lookback_days"]) if s else None
    if not td:
        return Signal("Dolar endeksi (DXY)", YOK, "veri yok")
    latest, prev, delta = td
    pct = (latest / prev - 1.0) * 100.0 if prev else 0.0
    lbl = label_dxy(pct, ic["thresholds"]["dxy_pct"])
    return Signal("Dolar endeksi (DXY)", lbl, f"{pct:+.2f}% (~1ay)")


def ons_gma_signal(cfg: dict) -> Signal:
    ic = cfg["indicators"]
    try:
        import yfinance as yf
        close = None
        for tk in (ic["ons_ticker"], "XAUUSD=X", "GLD"):
            h = yf.Ticker(tk).history(period="1y", interval="1d")
            if not h.empty and h["Close"].dropna().shape[0] >= 200:
                close = h["Close"].dropna()
                break
        if close is None:
            return Signal("Ons 50/200 GMA", YOK, "yeterli tarih yok")
        price = float(close.iloc[-1])
        gma50 = float(close.tail(50).mean())
        gma200 = float(close.tail(200).mean())
        lbl = label_gma(price, gma50, gma200)
        return Signal("Ons 50/200 GMA", lbl,
                      f"fiyat {price:.0f} · 50G {gma50:.0f} · 200G {gma200:.0f}")
    except Exception as e:
        log.warning("ons GMA hata: %s", e)
        return Signal("Ons 50/200 GMA", YOK, "yfinance hatası")


OZ_PER_TONNE = 32150.7466


def gld_tonnes_now(cfg: dict) -> Optional[float]:
    """SPDR GLD güncel tonaj = AUM / altın_ons_fiyatı / (ons/ton).

    Eski arşiv CSV'si artık PDF dönüyor; yfinance GLD.info totalAssets kullanılır.
    """
    try:
        import yfinance as yf
        gld = yf.Ticker(cfg["indicators"].get("gld_ticker", "GLD"))
        aum = gld.info.get("totalAssets") or gld.info.get("netAssets")
        if not aum:
            return None
        # altın ons fiyatı
        ons = None
        h = yf.Ticker(cfg["indicators"]["ons_ticker"]).history(period="5d", interval="1d")
        if not h.empty:
            ons = float(h["Close"].dropna().iloc[-1])
        if not ons:
            return None
        return aum / ons / OZ_PER_TONNE
    except Exception as e:
        log.warning("GLD tonaj hesap hata: %s", e)
        return None


def gld_signal(cfg: dict) -> Signal:
    """SPDR GLD tonaj değişimi. Güncel tonaj AUM'dan; trend için günlük snapshot arşivi.

    İlk gözlemde 'veri birikiyor' (arşiv dolunca değişim hesaplanır) — prim arşivi mantığı.
    """
    from . import db
    ic = cfg["indicators"]
    tonnes = gld_tonnes_now(cfg)
    if tonnes is None:
        return Signal("SPDR GLD tonaj", YOK, "AUM/fiyat çekilemedi")

    con = db.connect(cfg)
    today = util.to_local(util.utcnow(), cfg.get("timezone_offset_hours", 3)).date().isoformat()
    con.execute("INSERT OR REPLACE INTO gld_tonnage(date,tonnes) VALUES(?,?)", (today, tonnes))
    con.commit()
    # trend: lookback gün öncesine en yakın snapshot
    rows = con.execute("SELECT date,tonnes FROM gld_tonnage ORDER BY date").fetchall()
    con.close()
    if len(rows) < 2:
        return Signal("SPDR GLD tonaj", YOK,
                      f"{tonnes:.0f} ton (1. gözlem — trend için arşiv birikiyor)")
    prev = rows[max(0, len(rows) - 1 - ic["trend_lookback_days"])]["tonnes"]
    pct = (tonnes / prev - 1.0) * 100.0 if prev else 0.0
    lbl = label_gld(pct, ic["thresholds"]["gld_ton_pct"])
    return Signal("SPDR GLD tonaj", lbl, f"{tonnes:.0f} ton, {pct:+.2f}%")


def real_deposit_signal(cfg: dict, reel_net_pct: Optional[float]) -> Signal:
    if reel_net_pct is None:
        return Signal("TL reel net mevduat", YOK, "EVDS verisi yok")
    thr = cfg["indicators"]["thresholds"]
    lbl = label_real_deposit(reel_net_pct, thr["reel_faiz_dusuk"], thr["reel_faiz_yuksek"])
    return Signal("TL reel net mevduat", lbl, f"{reel_net_pct:+.1f}% (altın fırsat maliyeti)")


def build_panel(cfg: dict, reel_net_pct: Optional[float] = None) -> dict:
    """Tüm göstergeleri toplar, uzlaşı skorunu döner."""
    signals = [
        real_rate_signal(cfg),
        dxy_signal(cfg),
        ons_gma_signal(cfg),
        real_deposit_signal(cfg, reel_net_pct),
        gld_signal(cfg),
    ]
    try:
        from .trends import trends_signal
        signals.append(trends_signal(cfg))
    except Exception as e:
        log.warning("trends göstergesi hata: %s", e)
    # Grafik göstergeleri (yapı/RSI/%B/seviye) fiyat türevi ve birbiriyle korelasyonlu;
    # panele 4 ayrı oy olarak girerlerse panel makro kılığında bir momentum göstergesine
    # döner (ons_gma zaten burada). Bu yüzden TEK toplu oy olarak girer.
    if cfg.get("chart", {}).get("panele_katil"):
        try:
            from .chart import build_chart
            c = build_chart(cfg)
            if not c.get("yok"):
                signals.append(Signal("Grafik teknik uzlaşısı", c["uzlasi"]["yon"],
                                      "skor %+d/%d" % (c["uzlasi"]["score"],
                                                       c["uzlasi"]["n"])))
        except Exception as e:
            log.warning("grafik göstergesi hata: %s", e)
    return {"signals": signals, "consensus": consensus(signals)}
