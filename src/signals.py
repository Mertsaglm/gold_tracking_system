"""Bölüm 3 — Sinyal motoru (on-demand; 7/24 gerektirmez).

Her sinyal PROJE-REHBERI 6.3 şemasıyla: gerekçe + güven + geçersizlik koşulu.
Backtest köprüsü: tarihsel karşılığı varsa istatistik iliştirir, yoksa açıkça belirtir.
Bildirim eşik değerlendirmesi (6.2); zamanlayıcı GitHub Actions'tadır.
"""
from __future__ import annotations

import logging
import math
import statistics
from typing import Optional

from . import calc, db, util

log = logging.getLogger("signals")

UYARI = "Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir."


def zscore_dry_run(cfg: dict, con) -> dict:
    """Z-skoru KAPIYI YOK SAYARAK hesaplar — sadece ölçüm, bildirim GÖNDERMEZ.

    Amaç: 60 günlük kapı açıldığında (~2026 Eylül) `z > 2` bildirimi ilk kez
    ateşlenecek ve o ana dek hiç denenmemiş olacak. Kalibrasyonsuz açılırsa
    beklenmedik sıklıkta alarm günlük tavanı (6) doldurup diğer bildirimleri
    bastırabilir. Bu fonksiyon her gün "z ne olurdu" sorusunu kayda geçirir;
    kapı açılmadan dağılım ve tetiklenme sıklığı bilinir.

    İKİ TABAN ölçülür çünkü tutarsızlık var: kapı GÜN sayıyor (Faz 7) ama
    mevcut z hesabı TÜM KAYITLAR üzerinden yapılıyor. Gün içi ~10 örnek
    birbirinin tekrarı olduğundan std'yi bozar. Hangisinin doğru olduğunu
    kapı açılmadan bu prova gösterir.
    """
    zmin = cfg["stats"]["zscore_min_samples"]
    esik = cfg.get("alerts", {}).get("prim_z", 2.0)
    n_days = db.count_valid_prim_days(con)

    def _z(seri: list[float]):
        """Kapıyı yok sayar (min_samples=2) — amaç ölçüm, sinyal değil."""
        if len(seri) < 3:
            return None, None, None
        z = calc.zscore(seri[:-1], seri[-1], 2)
        return z.value, z.mean, z.std

    kayitlar = db.prim_series(con)
    gunluk = [v for _, v in db.prim_daily_means(con)]
    z_kayit, mu_k, sd_k = _z(kayitlar)
    z_gun, mu_g, sd_g = _z(gunluk)

    # Çeyrek primi z'si de aynı kapıya tabi ve o da kapı açılana dek HİÇ
    # ateşlenmemiş olacak → aynı kalibrasyon riski, aynı prova.
    q_kayit = db.prim_series(con, column="quarter_prim_pct")
    q_gunluk = [v for _, v in db.prim_daily_means(con, column="quarter_prim_pct")]
    qz_kayit, _, _ = _z(q_kayit)
    qz_gun, _, _ = _z(q_gunluk)
    q_esik = cfg.get("alerts", {}).get("quarter_z", 2.0)

    return {
        "ceyrek_z_esigi": q_esik,
        "ceyrek_z_kayit": qz_kayit,
        "ceyrek_z_gun": qz_gun,
        "ceyrek_tetiklenir_kayit": (qz_kayit is not None and abs(qz_kayit) > q_esik),
        "ceyrek_tetiklenir_gun": (qz_gun is not None and abs(qz_gun) > q_esik),
        "gun": n_days,
        "esik_gun": zmin,
        "kapi_acik": n_days >= zmin,
        "n_kayit": len(kayitlar),
        "n_gun": len(gunluk),
        "z_esigi": esik,
        # mevcut yöntem: tüm kayıtlar
        "z_kayit_tabani": z_kayit,
        "ort_kayit": mu_k,
        "std_kayit": sd_k,
        "tetiklenir_kayit": (z_kayit is not None and abs(z_kayit) > esik),
        # önerilen taban: günlük ortalamalar (kapıyla tutarlı)
        "z_gun_tabani": z_gun,
        "ort_gun": mu_g,
        "std_gun": sd_g,
        "tetiklenir_gun": (z_gun is not None and abs(z_gun) > esik),
    }


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
    n_days = db.count_valid_prim_days(con)
    if latest is None:
        out.append(_signal("prim_zskoru", "veri_bekliyor", ["birikimci"],
                           ["Henüz prim verisi yok."], "yok",
                           "Toplayıcı çalışıp arşiv birikince geçerli olur.", "—"))
    elif n_days < zmin:
        out.append(_signal("prim_zskoru", "veri_bekliyor", ["birikimci", "makasçı"],
                           [f"Canlı prim arşivi yetersiz ({n_days}/{zmin} gün).",
                            f"Güncel prim {latest['prim_pct']:+.2f}% ama z-skor için tarihçe eksik."],
                           "yok",
                           f"Arşiv {zmin} güne ulaşınca z-skor sinyali devreye girer.", "—"))
    else:
        series = db.prim_series(con)
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


# ---------- Bildirim eşik değerlendirmesi (rehber 6.2) — zamanlayıcı Actions'ta ----------
def evaluate_alerts(cfg: dict) -> list[dict]:
    """Eşik değerlendirmesinin CLI görünümü — `python -m src.signals alerts`.

    TEK KAYNAK: kural mantığı `notify.evaluate_thresholds`'tadır; burası yalnız
    onu çağırıp CLI çıktısına dönüştürür.

    Neden: bu fonksiyonun kendi kopyası vardı ve sessizce AYRIŞMIŞTI — üretim
    (notify) 5 kural uygularken burası yalnız 3'ünü biliyordu (`makas` ve
    `ceyrek_prim` eksikti). İki ayrı yerde tutulan eşik mantığı er geç ayrışır;
    eşik değiştirmek isteyen tek yere bakmalı.
    """
    from . import notify
    ctx = notify.build_context(cfg)
    return [
        {"tip": a["tip"], "deger": a["deger"], "mesaj": a["gerekce"]}
        for a in notify.evaluate_thresholds(ctx, cfg)
    ]


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
