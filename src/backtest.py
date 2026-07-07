"""Bölüm 2 — Backtest motoru (rehber 4.2 metodolojisi).

Çekirdek fonksiyonlar SAF ve testlidir. Look-ahead koruması: sinyal günü t ise
giriş t+1 (sonraki işlem günü) fiyatıyla.

- dist_stats: getiri dağılımı özeti (N, medyan, ortalama, p25-p75, kazanma, en kötü).
- forward_returns: sinyal günleri → ileri getiri dağılımı.
- regime_label: A/B/C/D/X rejim etiketleyici (saf).
- dca_simulate / deposit_simulate: birikim karşılaştırması.
"""
from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

log = logging.getLogger("backtest")


# ---------- İstatistik ----------
def _pct(sorted_vals, q):
    if not sorted_vals:
        return None
    idx = q * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)


def dist_stats(returns: Sequence[float], weak_n: int = 15) -> dict:
    """Getiri (yüzde) dağılımı özeti."""
    r = [x for x in returns if x is not None]
    n = len(r)
    if n == 0:
        return {"n": 0, "weak": True, "note": "veri yok"}
    s = sorted(r)
    return {
        "n": n,
        "weak": n < weak_n,
        "medyan": statistics.median(s),
        "ortalama": statistics.mean(s),
        "p25": _pct(s, 0.25),
        "p75": _pct(s, 0.75),
        "kazanma_pct": sum(1 for x in r if x > 0) / n * 100.0,
        "en_kotu": min(r),
        "en_iyi": max(r),
    }


# ---------- İleri getiri (look-ahead korumalı) ----------
def forward_returns(
    dates: Sequence[str],
    prices: Sequence[float],
    signal_idx: Sequence[int],
    horizon: int,
) -> list[float]:
    """Sinyal indeksi t için giriş t+1, çıkış t+1+horizon. Getiri yüzde.

    dates/prices tarih-sıralı paralel diziler. Sınır dışı sinyaller atlanır.
    """
    out = []
    n = len(prices)
    for t in signal_idx:
        enter = t + 1
        exit_ = t + 1 + horizon
        if exit_ >= n or enter >= n:
            continue
        p0, p1 = prices[enter], prices[exit_]
        if p0 and p1:
            out.append((p1 / p0 - 1.0) * 100.0)
    return out


def forward_returns_nonoverlap(
    dates: Sequence[str],
    prices: Sequence[float],
    signal_idx: Sequence[int],
    horizon: int,
) -> list[float]:
    """Örtüşmeyen ileri getiriler: bir pencere kullanılınca sonraki giriş en az
    'horizon' gün ileriden seçilir → bağımsız örneklem (şişkin N ve abartılı
    kazanma oranı düzeltmesi).
    """
    out = []
    n = len(prices)
    last_used_exit = -1
    for t in sorted(signal_idx):
        enter = t + 1
        if enter <= last_used_exit:          # önceki pencereyle örtüşüyor → atla
            continue
        exit_ = enter + horizon
        if exit_ >= n:
            continue
        p0, p1 = prices[enter], prices[exit_]
        if p0 and p1:
            out.append((p1 / p0 - 1.0) * 100.0)
            last_used_exit = exit_
    return out


def effective_periods(n_days: int, horizon: int) -> int:
    """Örtüşen günlük pencerelerin kaba etkin (bağımsız) dönem tahmini."""
    return max(1, n_days // horizon) if horizon else n_days


# ---------- Rejim etiketleme ----------
def regime_label(
    ons: float, gma200: Optional[float],
    real_rate_delta: Optional[float],   # DFII10 son − N gün önce (yüzde puan); <0 düşüş
    kur_vol_annual: Optional[float],    # yıllıklaştırılmış % oynaklık
    kur_vol_threshold: float,
) -> str:
    """A/B/C/D/X. Rehber 2.3 + rejim D dipnotu.

    A: ons>200GMA, reel faiz ↓, kur baskılanıyor (düşük vol)
    B: ons>200GMA, reel faiz ↓, kur serbest (yüksek vol)
    C: ons<200GMA, reel faiz ↑
    D: ons>200GMA, reel faiz ↑ (anomali — altın yükselirken reel faiz de yükseliyor;
       merkez bankası alım rejimi benzeri, klasik korelasyon bozuk)
    X: sınıflanamayan (veri eksik veya karışık kombinasyon)
    """
    if gma200 is None or real_rate_delta is None or kur_vol_annual is None:
        return "X"
    above = ons > gma200
    rate_falling = real_rate_delta < 0
    kur_bask = kur_vol_annual < kur_vol_threshold
    if above and rate_falling:
        return "A" if kur_bask else "B"
    if (not above) and (not rate_falling):
        return "C"
    if above and (not rate_falling):
        return "D"
    return "X"


# ---------- DCA / mevduat simülasyonu ----------
@dataclass
class DcaResult:
    yatirilan: float
    birim: float          # biriken gram
    deger: float          # son fiyatla değer
    getiri_pct: float
    max_dd_pct: float


def dca_simulate(
    month_keys: Sequence[str],          # ISO ay-başı, alım günleri
    month_prices: dict,                 # {ay-başı: gram fiyat}
    amount: float,
    buy_condition: Optional[Callable[[str], bool]] = None,
) -> DcaResult:
    """Aylık DCA: her uygun ayda 'amount' TL ile gram al. Koşul verilirse filtreler."""
    units = 0.0
    invested = 0.0
    equity_curve = []
    for mk in month_keys:
        price = month_prices.get(mk)
        if not price:
            continue
        if buy_condition and not buy_condition(mk):
            # o ay alım yok ama portföy değeri güncellenir
            equity_curve.append(units * price)
            continue
        units += amount / price
        invested += amount
        equity_curve.append(units * price)
    last_price = month_prices.get(month_keys[-1]) if month_keys else None
    value = units * last_price if last_price else 0.0
    ret = (value / invested - 1.0) * 100.0 if invested else 0.0
    max_dd = _max_drawdown(equity_curve)
    return DcaResult(invested, units, value, ret, max_dd)


def dca_conditional_deposit(
    month_keys: Sequence[str],
    month_prices: dict,
    monthly_rate_pct: dict,
    amount: float,
    stopaj_pct: float,
    buy_condition: Callable[[str], bool],
):
    """Prim-koşullu DCA — ADİL: alım yapılmayan ayların nakdi mevduatta net faizle
    işler (ölü nakit değil), sonraki alım ayında altına konuşlanır.

    Döner: (DcaResult, {atlanan_ay, ortalama_bekleme}).
    """
    units = 0.0
    dry = 0.0            # bekleyen nakit (mevduatta faiz işler)
    invested = 0.0
    skipped = 0
    wait_run = 0
    wait_runs = []
    curve = []
    for mk in month_keys:
        rate = monthly_rate_pct.get(mk)
        if rate is not None:
            net_monthly = (rate * (1 - stopaj_pct / 100.0) / 100.0) / 12.0
            dry *= (1 + net_monthly)
        price = month_prices.get(mk)
        invested += amount
        if buy_condition(mk) and price:
            units += (amount + dry) / price
            dry = 0.0
            if wait_run:
                wait_runs.append(wait_run)
                wait_run = 0
        else:
            dry += amount
            skipped += 1
            wait_run += 1
        curve.append(units * (price or 0) + dry)
    last = month_prices.get(month_keys[-1]) if month_keys else None
    value = units * (last or 0) + dry
    ret = (value / invested - 1.0) * 100.0 if invested else 0.0
    avg_wait = (sum(wait_runs) / len(wait_runs)) if wait_runs else 0.0
    return (DcaResult(invested, units, value, ret, _max_drawdown(curve)),
            {"atlanan_ay": skipped, "ortalama_bekleme_ay": avg_wait})


def _max_drawdown(curve: Sequence[float]) -> float:
    peak = -math.inf
    mdd = 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, (v / peak - 1.0))
    return mdd * 100.0


def deposit_simulate(
    month_keys: Sequence[str],
    monthly_rate_pct: dict,             # {ay-başı: yıllık brüt mevduat faizi %}
    amount: float,
    stopaj_pct: float,
) -> DcaResult:
    """Aylık DCA'nın mevduat karşılığı: her ay 'amount' yatır, net faizle bileşik büyüt."""
    balance = 0.0
    invested = 0.0
    curve = []
    for mk in month_keys:
        rate = monthly_rate_pct.get(mk)
        # aylık net faiz = yıllık brüt × (1−stopaj) / 12
        if rate is not None:
            net_monthly = (rate * (1 - stopaj_pct / 100.0) / 100.0) / 12.0
            balance *= (1 + net_monthly)
        balance += amount
        invested += amount
        curve.append(balance)
    ret = (balance / invested - 1.0) * 100.0 if invested else 0.0
    return DcaResult(invested, 0.0, balance, ret, _max_drawdown(curve))


# ===================== Gerçek veriyle rapor =====================
def _rolling_mean(vals, i, window):
    lo = max(0, i - window + 1)
    seg = vals[lo:i + 1]
    return sum(seg) / len(seg) if seg else None


def _annual_vol(logrets, i, window):
    lo = max(0, i - window + 1)
    seg = logrets[lo:i + 1]
    if len(seg) < 5:
        return None
    return statistics.pstdev(seg) * math.sqrt(252) * 100.0


def _load_history(con):
    rows = con.execute(
        "SELECT date,ons_usd,usdtry,gram_teorik FROM history_daily ORDER BY date"
    ).fetchall()
    return [dict(r) for r in rows]


def _fred_aligned(cfg, dates):
    """DFII10'u tarihlere hizala (ileri doldurma)."""
    from .indicators import _fred_csv
    series = _fred_csv(cfg, cfg["indicators"]["real_rate_series"]) or []
    smap = dict(series)
    out, last = [], None
    fred_sorted = sorted(smap)
    j = 0
    for d in dates:
        while j < len(fred_sorted) and fred_sorted[j] <= d:
            last = smap[fred_sorted[j]]
            j += 1
        out.append(last)
    return out


def _label_regimes(cfg, hist, dfii):
    bc = cfg["backtest"]
    gma_w = bc["gma_window"]
    rr_days = bc["real_rate_trend_days"]
    vol_w = bc["kur_vol_window"]
    thr = bc["kur_vol_annual_threshold_pct"]
    ons = [h["ons_usd"] for h in hist]
    usd = [h["usdtry"] for h in hist]
    logret = [0.0] + [math.log(usd[i] / usd[i - 1]) if usd[i - 1] else 0.0
                      for i in range(1, len(usd))]
    labels = []
    for i in range(len(hist)):
        gma = _rolling_mean(ons, i, gma_w) if i >= gma_w - 1 else None
        rr_delta = None
        if dfii[i] is not None and i >= rr_days and dfii[i - rr_days] is not None:
            rr_delta = dfii[i] - dfii[i - rr_days]
        kvol = _annual_vol(logret, i, vol_w) if i >= vol_w else None
        labels.append(regime_label(ons[i], gma, rr_delta, kvol, thr))
    return labels


def _month_start_prices(hist):
    """Her ayın ilk işlem gününü ay-başı ISO anahtarına bağla → {YYYY-MM-01: gram_teorik}."""
    seen, out = set(), {}
    for h in hist:
        ym = h["date"][:7]
        if ym not in seen:
            seen.add(ym)
            out[f"{ym}-01"] = h["gram_teorik"]
    return out


def _monthly_deposit_rate(con, code):
    """Haftalık mevduat faizinden ay-başı değer (o aya ait ilk gözlem)."""
    rows = con.execute(
        "SELECT date,value FROM evds_daily WHERE series_code=? AND value IS NOT NULL ORDER BY date",
        (code,)).fetchall()
    out = {}
    for r in rows:
        mk = f"{r['date'][:7]}-01"
        out.setdefault(mk, r["value"])
    return out


def _tufe_factor(con, code, start_mk, end_mk):
    """TÜFE endeks oranı. Ay eksikse ≤ hedef en yakın mevcut aya düşer."""
    rows = sorted((r["date"][:7], r["value"]) for r in con.execute(
        "SELECT date,value FROM evds_daily WHERE series_code=? AND value IS NOT NULL", (code,)))
    if not rows:
        return None

    def nearest(target):
        best = None
        for ym, v in rows:
            if ym <= target:
                best = v
            else:
                break
        return best or (rows[0][1])

    a = nearest(start_mk[:7])
    b = nearest(end_mk[:7])
    if a and b:
        return b / a
    return None


def _regime_stats_table(hist, labels, horizon):
    """Örtüşmeyen pencerelerle rejim istatistikleri + '_baseline' (tüm günler) satırı."""
    dates = [h["date"] for h in hist]
    gram = [h["gram_teorik"] for h in hist]
    ons = [h["ons_usd"] for h in hist]
    all_idx = list(range(len(hist)))
    rows = {"_baseline": {
        "gun": len(hist),
        "eff": effective_periods(len(hist), horizon),
        "gram_tl": dist_stats(forward_returns_nonoverlap(dates, gram, all_idx, horizon)),
        "usd": dist_stats(forward_returns_nonoverlap(dates, ons, all_idx, horizon)),
    }}
    by = {}
    for i, lab in enumerate(labels):
        by.setdefault(lab, []).append(i)
    for lab, idxs in sorted(by.items()):
        rows[lab] = {
            "gun": len(idxs),
            "eff": effective_periods(len(idxs), horizon),
            "gram_tl": dist_stats(forward_returns_nonoverlap(dates, gram, idxs, horizon)),
            "usd": dist_stats(forward_returns_nonoverlap(dates, ons, idxs, horizon)),
        }
    return rows


def _fmt_stat(s, baseline=None):
    if s.get("n", 0) == 0:
        return "veri yok"
    tag = " ⚠️zayıf" if s.get("weak") else ""
    base = ""
    if baseline and baseline.get("n"):
        diff = s["medyan"] - baseline["medyan"]
        base = f" · taban {baseline['medyan']:+.1f}% · **fark {diff:+.1f}p**"
    return (f"med {s['medyan']:+.1f}% · kaz %{s['kazanma_pct']:.0f} · "
            f"N={s['n']}{tag}{base}")


def run(cfg: dict) -> str:
    from . import db, logging_setup, util
    logging_setup.setup("backtest", cfg)
    con = db.connect(cfg)
    hist = _load_history(con)
    if len(hist) < 300:
        con.close()
        raise RuntimeError("history_daily yetersiz — önce: python -m src.history build")

    dfii = _fred_aligned(cfg, [h["date"] for h in hist])
    labels = _label_regimes(cfg, hist, dfii)
    bc = cfg["backtest"]
    oos = bc["oos_split"]
    ev = cfg["sources"]["evds"]["series"]
    stopaj = cfg["sources"]["evds"].get("mevduat_stopaj_pct", 15.0)

    L = ["# 📈 Altın Backtest Raporu", "",
         f"Veri: {hist[0]['date']} → {hist[-1]['date']} ({len(hist)} gün) · "
         f"ons kaynak GC=F (futures) · gram = teorik has.", "",
         "> Yöntem: look-ahead korumalı (giriş sinyal+1 gün). USD bazlı getiri = ons getirisi "
         "(kur etkisi arındırılmış). Gram TL = teorik has gram (canlı prim arşivi dolunca "
         "prim etkisi eklenecek — şu an aylık külçe proxy ayrı bölümde).", ""]

    # --- Rejim dağılımı ---
    from collections import Counter
    cnt = Counter(labels)
    L += ["## Rejim Dağılımı (2016→bugün)", "",
          "| Rejim | Gün | Tanım |", "|---|---|---|",
          f"| A | {cnt.get('A',0)} | ons>200GMA, reel faiz↓, kur baskılı |",
          f"| B | {cnt.get('B',0)} | ons>200GMA, reel faiz↓, kur serbest |",
          f"| C | {cnt.get('C',0)} | ons<200GMA, reel faiz↑ |",
          f"| D | {cnt.get('D',0)} | ons>200GMA, reel faiz↑ (anomali/MB alım rejimi) |",
          f"| X | {cnt.get('X',0)} | sınıflanamayan |", ""]

    # --- Rejim başına ileri getiri (3 ay, ÖRTÜŞMEYEN pencere + taban çizgisi) ---
    h63 = bc["horizons_days"]["3ay"]
    rstats = _regime_stats_table(hist, labels, h63)
    bl_g = rstats["_baseline"]["gram_tl"]
    bl_u = rstats["_baseline"]["usd"]
    L += ["## Rejim Başına 3 Ay İleri Getiri (örtüşmeyen pencere)", "",
          "> Örtüşen günlük pencereler bağımsız değil; **örtüşmeyen** pencere kullanıldı, "
          "her satırda **tabandan (tüm günler) fark** verildi. Bilgi değeri = farktır; "
          "mutlak medyan TL enflasyonu artefaktıdır.", "",
          "| Rejim | Gün(etkin) | Gram TL vs taban | Dolar bazlı (ons) vs taban |",
          "|---|---|---|---|",
          f"| **Taban (tüm günler)** | {rstats['_baseline']['gun']}"
          f"({rstats['_baseline']['eff']}) | med {bl_g['medyan']:+.1f}% · kaz %{bl_g['kazanma_pct']:.0f}"
          f" | med {bl_u['medyan']:+.1f}% · kaz %{bl_u['kazanma_pct']:.0f} |"]
    for lab in ["A", "B", "C", "D", "X"]:
        if lab in rstats:
            r = rstats[lab]
            L.append(f"| {lab} | {r['gun']}({r['eff']}) | "
                     f"{_fmt_stat(r['gram_tl'], bl_g)} | {_fmt_stat(r['usd'], bl_u)} |")
    L += ["", "_'Gün(etkin)' = takvim günü (kaba bağımsız dönem). Fark ≈0 veya negatifse "
          "rejimin bilgi değeri yok. Rehber iddiaları buna göre yeniden değerlendirildi._", ""]

    # --- Sinyal demo: ons 200GMA üstüne çıkış (golden cross) ---
    ons = [h["ons_usd"] for h in hist]
    dates = [h["date"] for h in hist]
    gram = [h["gram_teorik"] for h in hist]
    cross_idx = []
    for i in range(1, len(hist)):
        g0 = _rolling_mean(ons, i - 1, bc["gma_window"])
        g1 = _rolling_mean(ons, i, bc["gma_window"])
        if g0 and g1 and ons[i - 1] <= g0 and ons[i] > g1:
            cross_idx.append(i)
    all_idx = list(range(len(hist)))
    L += ["## Sinyal Demo: Ons 200GMA Üstüne Kırılım (taban karşılaştırmalı)", ""]
    for hn, hd in bc["horizons_days"].items():
        st = dist_stats(forward_returns_nonoverlap(dates, gram, cross_idx, hd))
        base = dist_stats(forward_returns_nonoverlap(dates, gram, all_idx, hd))
        L.append(f"- {hn}: {_fmt_stat(st, base)}")
    L += ["", f"_(Sinyal {len(cross_idx)} kez; örtüşmeyen pencerelerle N küçülür — "
          "kesinlik iddiası buna göre.)_", ""]

    # --- DCA karşılaştırması ---
    msp = _month_start_prices(hist)
    mks = sorted(msp)
    dep_rate = _monthly_deposit_rate(con, ev["mevduat_1yil"])
    amt = bc["dca_monthly_try"]
    # prim-koşullu: aylık külçe proxy prim < medyan iken al
    from .history import monthly_prim_proxy
    proxy = monthly_prim_proxy(cfg)
    prim_map = {p["date"]: p["prim_pct"] for p in proxy.get("series", [])}
    prim_median = statistics.median(prim_map.values()) if prim_map else 0.0

    def dca_block(title, keys):
        if len(keys) < 6:
            return [f"### {title}", "_yetersiz ay_", ""]
        u = dca_simulate(keys, msp, amt)
        c, extra = dca_conditional_deposit(
            keys, msp, dep_rate, amt, stopaj,
            buy_condition=lambda mk: prim_map.get(mk, 1e9) < prim_median)
        d = deposit_simulate(keys, dep_rate, amt, stopaj)
        tf = _tufe_factor(con, ev["tufe"], keys[0], keys[-1])
        def real(nom):
            return ((1 + nom / 100) / tf - 1) * 100 if tf else None
        def rr(nom):
            v = real(nom)
            return f"{v:+.0f}%" if v is not None else "—"
        b = [f"### {title} ({keys[0]}→{keys[-1]}, {len(keys)} ay)", "",
             "| Strateji | Nominal | TÜFE-reel | Maks. geri çekilme |",
             "|---|---|---|---|",
             f"| DCA koşulsuz (aylık gram) | {u.getiri_pct:+.0f}% | {rr(u.getiri_pct)} | {u.max_dd_pct:.0f}% |",
             f"| DCA prim-koşullu (nakit mevduatta) | {c.getiri_pct:+.0f}% | {rr(c.getiri_pct)} | {c.max_dd_pct:.0f}% |",
             f"| TL mevduat (EVDS 1yıl, net=brüt×{1-stopaj/100:.2f}) | {d.getiri_pct:+.0f}% | {rr(d.getiri_pct)} | — |",
             "",
             f"_Prim-koşullu: {extra['atlanan_ay']}/{len(keys)} ay atlandı (nakit mevduatta faiz "
             f"işledi), ort. bekleme {extra['ortalama_bekleme_ay']:.1f} ay._", ""]
        return b

    L += ["## DCA Karşılaştırması (aylık birikim)", "",
          f"_Prim-koşullu alım aylık külçe proxy (saflık bazı: {proxy.get('basis','?')}); "
          f"aylık çözünürlük — günlük prim değil. Alınmayan ay nakdi EVDS mevduatında net "
          f"faizle işler (adil karşılaştırma). Mevduat faizi = EVDS TP.TRY.MT06 tarihsel serisi._", ""]
    L += dca_block("Tüm dönem", mks)

    # --- Out-of-sample ---
    ins = [k for k in mks if k < oos]
    oosk = [k for k in mks if k >= oos]
    L += ["## Out-of-Sample Disiplini", "",
          f"Parametre/eşik dönemi (in-sample) < {oos}, test dönemi ≥ {oos}. Ayrı raporlanır.", ""]
    L += dca_block(f"In-sample (< {oos})", ins)
    L += dca_block(f"Out-of-sample (≥ {oos})", oosk)

    # rejim OOS
    def regime_counts(sub):
        return Counter(sub)
    n_ins = sum(1 for h in hist if h["date"] < oos)
    L += ["### Rejim dağılımı OOS kırılımı", "",
          f"- In-sample gün: {n_ins} · Out-of-sample gün: {len(hist)-n_ins}", ""]

    L += ["---", "_Genel bilgilendirme; yatırım tavsiyesi değildir. Geçmiş performans "
          "gelecek getiriyi garanti etmez._"]

    con.close()
    text = "\n".join(L)
    path = util.abspath(cfg["paths"]["reports_dir"]) / "backtest_raporu.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    log.info("backtest raporu: %s", path)
    return str(path)


if __name__ == "__main__":
    from . import util
    util.load_env()
    print(run(util.load_config()))
