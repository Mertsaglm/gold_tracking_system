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
from typing import Optional

from . import calc, db, util
from .market_calendar import MarketCalendar

log = logging.getLogger("import_actions")


def _f(v):
    try:
        return float(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None


def kirli_pencere(ts, pencereler) -> Optional[str]:
    """Kayıt bir "kirli kaynak" penceresine düşüyorsa pencerenin adını döner.

    NEDEN KOD, NEDEN DB DEĞİL: `insert_prim` INSERT OR REPLACE ve `import_all`
    HER GÜN tüm arşivi baştan okuyor. Kayıtları DB'de elle işaretlemek işe
    YARAMAZ — bir sonraki Actions koşumu CSV'den yeniden hesaplayıp üzerine
    yazar ve işaret sessizce kaybolur. Kural import yolunda durmalı ki her
    koşumda yeniden uygulansın.

    NEDEN CSV'Yİ DÜZELTMİYORUZ: `data/archive/*.csv` HAM GÖZLEM kaydıdır. O
    anki gerçek spot ons'u bilmiyoruz (yalnız günlük kapanış bar'ı var, o da
    gün-içi bir gözlem değil). Ham veriyi tahminle yeniden yazmak ölçümü
    uydurmaya çevirirdi; bilmediğimizi "bilmiyoruz" diye işaretlemek dürüst olan.
    """
    for p in pencereler or []:
        if p["baslangic_utc"] <= ts < p["bitis_utc"]:
            return p["ad"]
    return None


def turetilmis_gunler(cfg: dict, files, cal) -> dict:
    """Gün → piyasa bacağı teorik bacaktan TÜRETİLMİŞ mi (bağımsızlık nöbetçisi).

    İki bacak da AYNI satıcıdan alınır (Truncgil ons + Truncgil usd_mid); araya
    yfinance kuru sokulursa onun gürültüsü kimliği maskeler. Yalnız forex AÇIK
    kayıtlar sayılır: hafta sonu tüm alanlar donduğu için oran zaten sabittir ve
    "türetilmiş" gibi görünür — o günler `weekend=1` ile zaten tabandan düşüyor.

    Kayıt sayısı yetersiz günlerde (Actions ritmi düştüğünde) hüküm verilemez;
    o günler EN SON hüküm verilebilmiş günün kararını taşır (carry-forward).
    Sessizce "temiz" saymak, kimliğin kapı sayacına sızmasına izin verirdi.
    """
    sc = cfg["stats"]
    if not sc.get("bagimsizlik_nobetcisi_aktif", False):
        return {}
    esik = float(sc["bagimsizlik_cv_esigi"])
    min_kayit = int(sc["bagimsizlik_min_kayit"])
    troy = cfg["instruments"]["troy_ounce_gram"]
    gun_oranlari: dict = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ts_iso = row.get("ts_utc")
                if not ts_iso:
                    continue
                ts = datetime.fromisoformat(ts_iso).astimezone(timezone.utc)
                if cal.is_weekend_closed_forex(ts) or cal.is_us_gold_holiday(ts):
                    continue
                ons = _f(row.get("ons_usd"))
                gram_has = _f(row.get("gram_has_sell"))
                ub, us = _f(row.get("usd_buy")), _f(row.get("usd_sell"))
                if not (ons and gram_has and ub and us):
                    continue
                theo = calc.theoretical_gram(ons, (ub + us) / 2.0, troy)
                if theo:
                    gun_oranlari.setdefault(ts_iso[:10], []).append(gram_has / theo)
    out: dict = {}
    son_hukum = None
    for gun in sorted(gun_oranlari):
        h = calc.turetilmis_mi(gun_oranlari[gun], esik, min_kayit)
        if h is None:
            h = son_hukum          # kayıt az → komşudan taşı
        else:
            son_hukum = h
        out[gun] = bool(h)
    return out


def import_all(cfg: dict) -> dict:
    from . import logging_setup
    logging_setup.setup("import_actions", cfg)
    cal = MarketCalendar(cfg)
    con = db.connect(cfg)
    inst = cfg["instruments"]
    files = sorted(glob.glob(str(util.abspath("data/archive") / "*.csv")))
    kirli_pencereler = cfg["stats"].get("prim_kirli_pencereler", [])
    # Bağımsızlık nöbetçisi: ÖNCE tüm arşivi tarayıp hangi günlerde piyasa
    # bacağının teorik bacaktan türetildiğini belirle (gün-içi ölçüm gerektiği
    # için satır satır karar verilemez), sonra o günleri işaretle.
    turetilmis = turetilmis_gunler(cfg, files, cal)
    n_ticks = n_prim = n_weekend = n_rows = n_kirli = n_turetilmis = 0

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
                # Bu iş HER GÜN tüm arşivi baştan okuyor (dosya bazlı artımlılık
                # yok). `insert_tick` artık tekil: daha önce yazılmış bir gözlem
                # 0 döner ve o gözlemin `ohlc_1m` sayacı tekrar artırılmaz —
                # yoksa yeniden okuma her turda `n`'i şişirirdi.
                for sym, (bk, sk) in sym_map.items():
                    b, s = _f(row.get(bk)), _f(row.get(sk))
                    if b is None and s is None:
                        continue
                    if not db.insert_tick(con, ts_iso, "gh_actions", sym, b, s):
                        continue
                    n_ticks += 1
                    if s is not None:
                        db.update_ohlc(con, minute, sym, s)
                ons = _f(row.get("ons_usd"))
                usd = _f(row.get("usdtry"))
                for sym, val in (("ons_usd", ons), ("usdtry", usd)):
                    if val is not None:
                        if not db.insert_tick(con, ts_iso, "gh_actions", sym,
                                              None, val):
                            continue
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
                    # Kirli kaynak penceresi (ADR #013): kayıt teknik olarak
                    # üretildi ama TEORİK BACAĞI yanlış enstrümandan geldi.
                    # `indicative=1` işaretlenir → `prim_series` ve
                    # `count_valid_prim_days` ikisi de dışlar, yani z-skor
                    # tabanına ve 60 günlük kapı sayacına GİRMEZ.
                    kirli = kirli_pencere(ts_iso, kirli_pencereler)
                    # Türetilmiş gün: kayıt teknik olarak üretildi ama iki bacak
                    # bağımsız değil → prim ölçüm taşımıyor (bkz. nöbetçi).
                    tur = turetilmis.get(ts_iso[:10], False) and not forex_closed
                    db.insert_prim(
                        con, ts_utc=ts_iso, ons_usd=ons, usdtry=usd,
                        theoretical=theo, market_has=gram_has, gram_retail=gram_retail,
                        prim_pct=prim, prim_pct_naive=prim_naive, spread_pct=spread,
                        quarter_prim_pct=qp,
                        indicative=1 if (forex_closed or kirli or tur) else 0,
                        weekend=1 if weekend else 0, holiday=1 if holiday else 0,
                        reason=(f"kirli_kaynak:{kirli}" if kirli else
                                "turetilmis" if tur else
                                "gh_actions_import" + ("_weekend" if forex_closed else "")),
                    )
                    n_prim += 1
                    if kirli:
                        n_kirli += 1
                    if tur:
                        n_turetilmis += 1
                    if weekend:
                        db.insert_weekend_exp(con, ts_iso, gram_has, theo, prim)
                        n_weekend += 1
        con.commit()

    valid = db.count_valid_prim(con)
    con.close()
    result = {"dosya": len(files), "satir": n_rows, "tick": n_ticks,
              "prim": n_prim, "hafta_sonu": n_weekend, "kirli_kaynak": n_kirli,
              "turetilmis": n_turetilmis,
              "turetilmis_gun": sum(1 for v in turetilmis.values() if v),
              "gecerli_prim_toplam": valid}
    log.info("import: %s", result)
    return result


if __name__ == "__main__":
    util.load_env()
    print(import_all(util.load_config()))
