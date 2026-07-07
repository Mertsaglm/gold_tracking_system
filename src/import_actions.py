"""GitHub Actions CSV arşivini ana SQLite'a aktarır (Bölüm 1.3/1.4).

- ticks (source='gh_actions') + ohlc_1m
- prim_history: hafta içi = geçerli (indicative=0) → z-skor arşivini doldurur;
  forex kapalı (hafta sonu/tatil) = indicative=1, weekend=1 → weekend_expectation.
Böylece projenin ilk kesintisiz canlı arşivi ana veritabanına akar.
"""
from __future__ import annotations

import csv
import glob
import logging
from datetime import datetime, timezone

from . import calc, db, util
from .market_calendar import MarketCalendar

log = logging.getLogger("import_actions")


def _f(v):
    try:
        return float(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None


def import_all(cfg: dict) -> dict:
    from . import logging_setup
    logging_setup.setup("import_actions", cfg)
    cal = MarketCalendar(cfg)
    con = db.connect(cfg)
    inst = cfg["instruments"]
    files = sorted(glob.glob(str(util.abspath("data/archive") / "*.csv")))
    n_ticks = n_prim = n_weekend = n_rows = 0

    for path in files:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ts_iso = row.get("ts_utc")
                if not ts_iso:
                    continue
                ts = datetime.fromisoformat(ts_iso).astimezone(timezone.utc)
                n_rows += 1
                minute = ts.strftime("%Y-%m-%dT%H:%M")

                # tick'ler
                sym_map = {
                    "gram_altin": ("gram_altin_buy", "gram_altin_sell"),
                    "gram_has_altin": ("gram_has_buy", "gram_has_sell"),
                    "ceyrek": ("ceyrek_buy", "ceyrek_sell"),
                    "usd": ("usd_buy", "usd_sell"),
                }
                for sym, (bk, sk) in sym_map.items():
                    b, s = _f(row.get(bk)), _f(row.get(sk))
                    if b is None and s is None:
                        continue
                    db.insert_tick(con, ts_iso, "gh_actions", sym, b, s)
                    n_ticks += 1
                    if s is not None:
                        db.update_ohlc(con, minute, sym, s)
                ons = _f(row.get("ons_usd"))
                usd = _f(row.get("usdtry"))
                for sym, val in (("ons_usd", ons), ("usdtry", usd)):
                    if val is not None:
                        db.insert_tick(con, ts_iso, "gh_actions", sym, None, val)
                        db.update_ohlc(con, minute, sym, val)
                        n_ticks += 1

                # prim
                gram_has = _f(row.get("gram_has_sell"))
                if ons and usd and gram_has:
                    theo = calc.theoretical_gram(ons, usd, inst["troy_ounce_gram"])
                    prim = calc.prim_pct(gram_has, theo)
                    gram_retail = _f(row.get("gram_altin_sell"))
                    prim_naive = calc.prim_pct(gram_retail, theo) if gram_retail else None
                    gh_b = _f(row.get("gram_has_buy"))
                    spread = calc.spread_pct(gh_b, gram_has) if gh_b else None
                    qp = None
                    ceyrek = _f(row.get("ceyrek_sell"))
                    if ceyrek:
                        c = inst["coins"]["ceyrek"]
                        qp = calc.quarter_prim_pct(ceyrek, gram_has, c["gross_g"], c["milyem"])

                    forex_closed = cal.is_weekend_closed_forex(ts) or cal.is_us_gold_holiday(ts)
                    weekend = cal.is_weekend_closed_forex(ts)
                    holiday = cal.is_us_gold_holiday(ts) or cal.is_tr_holiday(ts)
                    db.insert_prim(
                        con, ts_utc=ts_iso, ons_usd=ons, usdtry=usd,
                        theoretical=theo, market_has=gram_has, gram_retail=gram_retail,
                        prim_pct=prim, prim_pct_naive=prim_naive, spread_pct=spread,
                        quarter_prim_pct=qp,
                        indicative=1 if forex_closed else 0,
                        weekend=1 if weekend else 0, holiday=1 if holiday else 0,
                        reason="gh_actions_import" + ("_weekend" if forex_closed else ""),
                    )
                    n_prim += 1
                    if weekend:
                        db.insert_weekend_exp(con, ts_iso, gram_has, theo, prim)
                        n_weekend += 1
        con.commit()

    valid = db.count_valid_prim(con)
    con.close()
    result = {"dosya": len(files), "satir": n_rows, "tick": n_ticks,
              "prim": n_prim, "hafta_sonu": n_weekend, "gecerli_prim_toplam": valid}
    log.info("import: %s", result)
    return result


if __name__ == "__main__":
    util.load_env()
    print(import_all(util.load_config()))
