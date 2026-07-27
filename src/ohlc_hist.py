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

    BUGÜNÜN BARI YAZILMAZ (`drop_unclosed_bar` okuma yolunda zaten uygulanıyordu;
    burada YAZMA yoluna da bağlandı). Sebep: yfinance canlı sorguda "bugün" için
    daima bir satır döndürür — piyasa kapalıyken bile. Tarihsel backfill'de bu
    satırlar yok (ölçüldü: 2653 GC=F barının 0'ı hafta sonu), ama günlük koşum
    onları yazıyordu ve `_upsert` hiçbir zaman silmediği için KALICI oluyorlardı:
    üretimde 2026-07-25 (Cmt) ve 2026-07-26 (Paz) TRY=X satırları böyle oluştu,
    Pazar barı o=h=l=c ile sıfır aralıklıydı ve ATR'yi aşağı çekiyordu.
    Kayıp yok: lookback penceresi 10 gün, yani bugünün tam barı yarınki koşumda
    yazılır — `asof` zaten T−1 olduğu için karar yoluna bir gün gecikme yansımaz.
    """
    from datetime import timedelta
    n = int(lookback_days or cfg["chart"]["ohlc"].get("guncelleme_lookback_gun", 10))
    start = (util.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")
    bugun = util.local_today()
    con = db.connect(cfg)
    out = {}
    try:
        for sym in _symbols(cfg):
            rows = drop_weekend_bars(
                drop_unclosed_bar(_yf_daily_ohlc(sym, start), bugun))
            out[sym] = _upsert(con, sym, rows)
    finally:
        con.close()
    return {"start": start, "bugun_haric": bugun, "yazilan": out}


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


def drop_weekend_bars(bars: list) -> list:
    """Cumartesi/Pazar barlarını atar — bunlar gerçek seans DEĞİL, çekim artefaktı.

    ÖLÇÜLDÜ (üretim dump'ı, 2026-07-26): 2653 GC=F + 2748 TRY=X = 5401 tarihsel
    barın **sıfırı** hafta sonuna düşüyor. Yani meşru bir hafta sonu barı yok;
    tabloda görünen tek hafta sonu satırları canlı sorgunun ürettiği hayaletler
    (2026-07-25 ve 2026-07-26 TRY=X).

    NEDEN `drop_unclosed_bar` YETMİYOR: o yalnız `date >= bugün` olanı atar. Cumartesi
    koşumunda yazılan bar, Pazartesi koşumunda artık GEÇMİŞ tarihlidir; o filtreden
    geçer. İki filtre birlikte hem bugünü hem hafta sonunu kapatır.

    Bu barlar zararsız değil: 2026-07-25'in aralığı 0.2226 — önceki 10 gerçek barın
    ortalamasının (0.0404) **5.5 katı** — ve `kur_atr`'ı %7.17 şişiriyordu.
    Proje zaten hafta sonunu geçersiz sayıyor (`prim_history` her istatistik
    tabanında `indicative=0 AND weekend=0` filtreler); burada o kural eksikti.
    """
    from datetime import date
    out = []
    for b in bars:
        try:
            if date.fromisoformat(b["date"]).weekday() < 5:
                out.append(b)
        except (ValueError, KeyError, TypeError):
            out.append(b)          # tarihi çözemiyorsak eleme — veri kaybetme
    return out


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
