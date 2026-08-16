"""GitHub Actions arşiv çekici (Bölüm 1.3).

Truncgil + yfinance ons/kur çeker, ay-bazlı CSV'ye satır ekler. Keysiz kaynaklar;
workflow'a secret gömülmez. Timestamp veri çekim anından (UTC).

CSV: data/archive/YYYY-MM.csv  (canlı toplayıcıyla AYNI alan adları → import tutarlı)
"""
from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from pathlib import Path

from . import util
from .sources import truncgil, yf

FIELDS = ["ts_utc", "ons_usd", "usdtry",
          "gram_altin_buy", "gram_altin_sell",
          "gram_has_buy", "gram_has_sell",
          "ceyrek_buy", "ceyrek_sell",
          "usd_buy", "usd_sell"]


def _retry(fetch_fn, ok_fn, retries: int, backoff: float):
    """Kaynak boş/başarısız dönerse kısa aralıkla tekrar dener.

    retries=0 → tek deneme (eski davranışla birebir aynı). İlk başarılı sonucu
    döner; tüm denemeler başarısızsa son (en iyi çaba) sonucu döner — çökme yok.
    GitHub cron sıklığını değil, çalışan turdaki veri kalitesini iyileştirir.
    """
    res = fetch_fn()
    tries = 0
    while not ok_fn(res) and tries < retries:
        tries += 1
        if backoff > 0:
            time.sleep(backoff)
        res = fetch_fn()
    return res


def fetch_row(cfg: dict) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    sc = cfg.get("sources", {})
    retries = int(sc.get("fetch_retries", 0))
    backoff = float(sc.get("fetch_retry_backoff_s", 0))
    # truncgil boş dönerse (gram/çeyrek eksik → geçersiz kayıt) tekrar dene
    tc = _retry(lambda: truncgil.fetch(cfg), lambda s: s.ok, retries, backoff)
    # yfinance artık YALNIZ kur için (ons Truncgil'den — aşağıdaki nota bak),
    # o yüzden tekrar deneme koşulu da yalnız kur'a bakar.
    yfs = _retry(lambda: yf.fetch(cfg),
                 lambda s: s.usdtry is not None,
                 retries, backoff)
    def bs(sym):
        return tc.bs(sym) if tc.ok else (None, None)
    ga_b, ga_s = bs("gram_altin")
    gh_b, gh_s = bs("gram_has_altin")
    cy_b, cy_s = bs("ceyrek")
    usd_b, usd_s = bs("usd")
    ons_b, ons_s = bs("ons")
    # ONS SPOT: Truncgil'den. yfinance `GC=F` YEDEK DEĞİLDİR ve bilerek
    # kullanılmıyor — hafta içi VADELİ kontrat (2026-08: GCZ26 = spot+%1.39)
    # döndürüyor; 2026-07-29 roll'ünden sonra prim'i 1.25 puan bozdu ve
    # |prim|>%1.5 alarmını 4 gün üst üste yanlış ateşledi (08-11…08-14).
    # Sessiz bir yedek burada hatayı geri getirirdi. Truncgil düşerse gram_has
    # da düşer (ölçüldü 2026-07-29: geçersiz kayıtların 20/20'sinde 8 alan
    # BİRDEN boş) → kayıt zaten geçersiz; ayrı bir ons yedeği hiçbir şey kurtarmaz.
    ons = ons_s if ons_s is not None else ons_b
    return {
        "ts_utc": ts,
        "ons_usd": ons, "usdtry": yfs.usdtry,
        "gram_altin_buy": ga_b, "gram_altin_sell": ga_s,
        "gram_has_buy": gh_b, "gram_has_sell": gh_s,
        "ceyrek_buy": cy_b, "ceyrek_sell": cy_s,
        "usd_buy": usd_b, "usd_sell": usd_s,
    }


def append_row(cfg: dict, row: dict) -> str:
    ym = row["ts_utc"][:7]                      # YYYY-MM
    d = util.abspath("data/archive")
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{ym}.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    return str(path)


def main(cfg: dict) -> str:
    row = fetch_row(cfg)
    path = append_row(cfg, row)
    print(f"[archive] {row['ts_utc']} -> {path} "
          f"(ons={row['ons_usd']} gram_has_sell={row['gram_has_sell']})")
    return path


if __name__ == "__main__":
    util.load_env()
    main(util.load_config())
