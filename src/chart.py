"""Grafik yorumu — destek/direnç + çoklu gösterge teyidi (Bölüm 6).

Tasarım ilkeleri (proje kültürü gereği):

1. TÜM teknik hesap **ons USD (GC=F) gerçek OHLC** üzerinde yapılır. gram TL'de seviye
   ÜRETİLMEZ: TL serisi enflasyonla yapısal olarak yukarı kayar, 2 yıl önceki "direnç"
   bugün anlamsızdır (bkz. backtest.py:440-441 aynı uyarı). TL yalnızca ons seviyesinin
   **bugünkü kurla izdüşümü** olarak, kullanılan kur yazılarak gösterilir.

2. **Seviye geometridir, ölçüm değildir.** Bir seviyenin yön iddiası taşıyabilmesi için
   `validate()` ile örtüşmeyen pencere + taban çizgisi karşılaştırmasından geçmesi gerekir.
   Faz 3 denetimi, taban çizgisiz backtest iddialarının nasıl çöktüğünü gösterdi
   (rejim A "%88 kazanma" → "fark −0.2p, üstünlük YOK"). Bu modül aynı hataya düşmez:
   ölçülmemiş hiçbir şey için iddialı dil kullanılmaz.

3. **Look-ahead koruması:** bir pivot ancak k bar SONRA bilinebilir (`Pivot.confirm_idx`).
   Doğrulama harness'i bu gecikmeye uymak zorundadır, yoksa tüm ölçüm geçersizdir.

4. **Hacim ağırlıklandırması KULLANILMAZ.** GC=F hacmi ön-vade kontrat hacmidir ve vade
   geçişlerinde süreksizdir (ölçüm: 2016'da 143, bugün 44.361 — bu likidite göçü, kanaat
   değil); TRY=X hacmi sıfırdır. Hacimle ağırlıklandırmak gürültüyü titizlik kılığına sokar.

5. **MACD bilinçli olarak DIŞARIDA.** Aynı kapanış serisinin iki EMA'sı — panelde zaten
   bulunan 50/200 GMA ile neredeyse eşdoğrusal. Eklemek uzlaşı paydasını kopya bir oyla
   şişirir ve paneli kanıtın desteklediğinden daha emin gösterir; Faz 3'te cezalandırılan
   hata tam olarak budur.

Saf fonksiyonlar (eşikler literal argüman olarak geçer, cfg okumaz) testlidir;
ağ/DB dokunan kısımlar test edilmez — proje konvansiyonu.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional, Sequence

from .indicators import NOTR, OLUMLU, OLUMSUZ, YOK

log = logging.getLogger("chart")


# ============================================================================
# Pivotlar
# ============================================================================
@dataclass(frozen=True)
class Pivot:
    idx: int
    date: str
    price: float
    kind: str            # "tepe" | "dip"
    confirm_idx: int     # idx + k — seviye ancak BU barda bilinebilir (look-ahead koruması)


def find_pivots(highs: Sequence[float], lows: Sequence[float],
                dates: Sequence[str], k: int) -> list:
    """Fraktal swing pivot: i barı [i-k, i+k] penceresinin uç değeriyse pivot.

    Düz plato k adet sahte pivot üretmesin diye her iki yanda EN AZ BİR komşudan
    kesin olarak (strict) üstün/aşağı olma şartı aranır.
    """
    n = len(highs)
    if n == 0 or k <= 0 or n < 2 * k + 1:
        return []
    out = []
    for i in range(k, n - k):
        win_h = highs[i - k:i + k + 1]
        win_l = lows[i - k:i + k + 1]
        if highs[i] == max(win_h) and (
                any(highs[i] > highs[j] for j in range(i - k, i)) and
                any(highs[i] > highs[j] for j in range(i + 1, i + k + 1))):
            out.append(Pivot(i, dates[i], float(highs[i]), "tepe", i + k))
        if lows[i] == min(win_l) and (
                any(lows[i] < lows[j] for j in range(i - k, i)) and
                any(lows[i] < lows[j] for j in range(i + 1, i + k + 1))):
            out.append(Pivot(i, dates[i], float(lows[i]), "dip", i + k))
    return out


# ============================================================================
# Kümeleme ve seviyeler
# ============================================================================
def cluster_pivots(pivots: Sequence, tol_pct: float) -> list:
    """Fiyatı yakın pivotları tek kümeye toplar.

    Tolerans ÖLÇEKTEN BAĞIMSIZ (yüzde) — seri 1.050'den 4.070'e gittiği için mutlak
    fiyat toleransı yanlış olurdu.
    """
    if not pivots:
        return []
    ordered = sorted(pivots, key=lambda p: p.price)
    clusters = [[ordered[0]]]
    for p in ordered[1:]:
        ref = clusters[-1][0].price
        if ref > 0 and abs(p.price - ref) / ref * 100.0 <= tol_pct:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return clusters


@dataclass(frozen=True)
class Level:
    price: float         # üye fiyatların MEDYANI (aykırı pivota dayanıklı)
    lo: float
    hi: float            # bant = üyelerin min/max'ı
    kind: str            # "direnç" | "destek" | "karma"
    touches: int
    first_date: str
    last_date: str
    score: float


def _median(vals: Sequence[float]) -> float:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0


def _days_between(d1: str, d2: str) -> int:
    from datetime import date
    try:
        a = date(*[int(x) for x in d1.split("-")])
        b = date(*[int(x) for x in d2.split("-")])
        return abs((b - a).days)
    except (ValueError, TypeError):
        return 0


def score_level(touches: int, age_days: int, half_life_days: float,
                is_karma: bool, karma_carpani: float) -> float:
    """Seviye gücü = sqrt(dokunuş) × tazelik × karma primi.

    - sqrt: azalan verim — 6. dokunuş 2.'nin 3 katı bilgi taşımaz.
    - tazelik 0.5**(yaş/yarı ömür): 18 ay önce son kez dokunulmuş seviye, %40 hareket
      etmiş bir piyasada büyük ölçüde ilgisizdir.
    - karma primi: direncin sonradan destek olması (kutup değişimi), S/R içinde teorik
      dayanağı olan tek olgudur (önceki işlem hafızası).

    Skor yalnız GÖSTERİM SIRALAMASI içindir; olasılık olarak sunulmaz.
    """
    if touches <= 0:
        return 0.0
    fresh = 0.5 ** (age_days / half_life_days) if half_life_days > 0 else 1.0
    return math.sqrt(touches) * fresh * (karma_carpani if is_karma else 1.0)


def build_levels(clusters: Sequence, last_date: str, half_life_days: float,
                 min_touches: int, karma_carpani: float) -> list:
    """Kümeleri Level'a çevirir; min_touches altındakileri eler."""
    out = []
    for cl in clusters:
        if len(cl) < min_touches:
            continue
        prices = [p.price for p in cl]
        kinds = {p.kind for p in cl}
        kind = "karma" if len(kinds) > 1 else ("direnç" if "tepe" in kinds else "destek")
        dates = sorted(p.date for p in cl)
        age = _days_between(dates[-1], last_date)
        out.append(Level(
            price=_median(prices), lo=min(prices), hi=max(prices), kind=kind,
            touches=len(cl), first_date=dates[0], last_date=dates[-1],
            score=score_level(len(cl), age, half_life_days,
                              kind == "karma", karma_carpani)))
    return sorted(out, key=lambda L: L.price)


def nearest_levels(levels: Sequence, price: float, n: int) -> dict:
    """Spot'un altındaki destekler / üstündeki dirençler, yakından uzağa."""
    below = [L for L in levels if L.hi < price]
    above = [L for L in levels if L.lo > price]
    below.sort(key=lambda L: price - L.price)
    above.sort(key=lambda L: L.price - price)
    return {"destekler": below[:n], "direncler": above[:n]}


def extremes(highs: Sequence[float], lows: Sequence[float], dates: Sequence[str],
             windows: dict, spot: Optional[float] = None) -> dict:
    """Pencere başına zirve/dip ve spot'un onlara uzaklığı.

    windows: {"1y": 252, ...}; 0 = tüm geçmiş. spot verilmezse son yüksek kullanılır
    (uzaklık kapanışa göre ölçülmeli, o yüzden çağıran kapanışı geçmeli).
    """
    out = {}
    n = len(highs)
    if n == 0:
        return out
    spot = float(spot if spot is not None else highs[-1])
    for ad, w in windows.items():
        seg = slice(max(0, n - w), n) if w and w > 0 else slice(0, n)
        hs, ls, ds = highs[seg], lows[seg], dates[seg]
        if not hs:
            continue
        hi_i = max(range(len(hs)), key=lambda i: hs[i])
        lo_i = min(range(len(ls)), key=lambda i: ls[i])
        zirve, dip = float(hs[hi_i]), float(ls[lo_i])
        out[ad] = {
            "zirve": (ds[hi_i], zirve), "dip": (ds[lo_i], dip),
            "zirveden_uzaklik_pct": (spot / zirve - 1.0) * 100.0 if zirve else 0.0,
            "dipten_uzaklik_pct": (spot / dip - 1.0) * 100.0 if dip else 0.0,
        }
    return out


# ============================================================================
# Göstergeler (saf hesap)
# ============================================================================
def true_range(h: float, l: float, prev_c: Optional[float]) -> float:
    """Gerçek aralık. prev_c None ise (ilk bar) yalnız h-l."""
    if prev_c is None:
        return h - l
    return max(h - l, abs(h - prev_c), abs(l - prev_c))


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
        window: int) -> list:
    """Wilder ATR. Yetersiz veri için baştaki elemanlar None.

    history_daily kapanış-kapanış yaklaşımı (`signals.atr_proxy`) kullanmak zorundaydı;
    gerçek H/L geldiği için burada HAKİKİ ATR hesaplanır.
    """
    n = len(closes)
    out = [None] * n
    if n == 0 or window <= 0 or n < window:
        return out
    trs = [true_range(highs[i], lows[i], closes[i - 1] if i > 0 else None)
           for i in range(n)]
    prev = sum(trs[:window]) / window
    out[window - 1] = prev
    for i in range(window, n):
        prev = (prev * (window - 1) + trs[i]) / window
        out[i] = prev
    return out


def rsi(closes: Sequence[float], window: int) -> list:
    """Wilder RSI. Sabit seride bölme hatası olmaz (kayıp yoksa 100, kazanç yoksa 0)."""
    n = len(closes)
    out = [None] * n
    if n <= window or window <= 0:
        return out
    gains, losses = [], []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:window]) / window
    al = sum(losses[:window]) / window

    def _rsi(g, l):
        if l == 0:
            return 100.0 if g > 0 else 50.0     # sabit seri -> nötr 50
        return 100.0 - 100.0 / (1.0 + g / l)

    out[window] = _rsi(ag, al)
    for i in range(window + 1, n):
        ag = (ag * (window - 1) + gains[i - 1]) / window
        al = (al * (window - 1) + losses[i - 1]) / window
        out[i] = _rsi(ag, al)
    return out


def bollinger(closes: Sequence[float], window: int, k: float) -> list:
    """(orta, üst, alt, %B). Sabit seride sd=0 → %B None (inf değil)."""
    n = len(closes)
    out = [(None, None, None, None)] * n
    if n < window or window <= 0:
        return out
    for i in range(window - 1, n):
        seg = closes[i - window + 1:i + 1]
        mid = sum(seg) / window
        var = sum((x - mid) ** 2 for x in seg) / window
        sd = math.sqrt(var)
        up, dn = mid + k * sd, mid - k * sd
        pctb = None if sd == 0 else (closes[i] - dn) / (up - dn)
        out[i] = (mid, up, dn, pctb)
    return out


def swing_structure(pivots: Sequence, n: int) -> dict:
    """Son n tepe/dip karşılaştırması → HH/HL/LH/LL bayrakları."""
    tepe = [p for p in pivots if p.kind == "tepe"][-n:]
    dip = [p for p in pivots if p.kind == "dip"][-n:]
    hh = len(tepe) >= 2 and tepe[-1].price > tepe[-2].price
    lh = len(tepe) >= 2 and tepe[-1].price < tepe[-2].price
    hl = len(dip) >= 2 and dip[-1].price > dip[-2].price
    ll = len(dip) >= 2 and dip[-1].price < dip[-2].price
    return {"hh": hh, "hl": hl, "lh": lh, "ll": ll,
            "son_tepeler": [p.price for p in tepe],
            "son_dipler": [p.price for p in dip]}


# ============================================================================
# Etiketleyiciler (saf — eşikler literal argüman; indicators.py konvansiyonu)
# ============================================================================
def label_rsi(rsi_val: Optional[float], asiri_alim: float, asiri_satim: float) -> str:
    """Aşırı alım altın için OLUMSUZ, aşırı satım OLUMLU (kontrarian uçlar).

    Yön seçimi trends_z konvansiyonuyla aynı. AMA Faz 3'te Trends kontrarian hipotezi
    doğrulanamadı — bu yüzden etiket `validate()` ile ölçülür ve ölçülen taban farkı
    etiketin yanında yazılır. Etiket iddia değil, ölçüm iddiadır.
    """
    if rsi_val is None:
        return YOK
    if rsi_val > asiri_alim:
        return OLUMSUZ
    if rsi_val < asiri_satim:
        return OLUMLU
    return NOTR


def label_trend_structure(hh: bool, hl: bool, lh: bool, ll: bool) -> str:
    """HH+HL yükselen yapı (olumlu), LH+LL alçalan (olumsuz), karışık nötr."""
    if hh and hl:
        return OLUMLU
    if lh and ll:
        return OLUMSUZ
    return NOTR


def label_bollinger(pct_b: Optional[float], ust_thr: float, alt_thr: float) -> str:
    """Üst bandın üstü aşırı uzama (olumsuz), alt bandın altı (olumlu) — kontrarian."""
    if pct_b is None:
        return YOK
    if pct_b > ust_thr:
        return OLUMSUZ
    if pct_b < alt_thr:
        return OLUMLU
    return NOTR


def label_level_proximity(mesafe_atr: Optional[float], yakin_atr: float, yon: str) -> str:
    """Desteğe yakınlık olumlu, dirence yakınlık olumsuz; uzaksa nötr."""
    if mesafe_atr is None:
        return YOK
    if abs(mesafe_atr) > yakin_atr:
        return NOTR
    return OLUMLU if yon == "destek" else OLUMSUZ


def label_vol_regime(atr_pct: Optional[float], p33: float, p66: float) -> str:
    """Oynaklık rejimi — BİLGİ AMAÇLI, yönsüz olduğu için uzlaşı oylamasına GİRMEZ."""
    if atr_pct is None:
        return YOK
    if atr_pct < p33:
        return "düşük"
    if atr_pct > p66:
        return "yüksek"
    return "orta"


# ============================================================================
# Dürüst ölçüm verdiği
# ============================================================================
def edge_verdict(diff_p: Optional[float], n: int, weak_n: int, min_diff_p: float) -> str:
    """Taban çizgisine göre ölçülen farkın hükmü.

    Zayıf N, büyük farkı EZER — bu fonksiyonun bütün amacı budur. Faz 3'te iddiaları
    çökerten şey tam olarak az sayıda bağımsız gözlemdi.
    """
    if diff_p is None or n <= 0:
        return "ölçüm yok"
    if n < weak_n:
        return "ölçüm yetersiz (N=%d)" % n
    if abs(diff_p) < min_diff_p:
        return "kenar yok"
    return "zayıf kanıt: %+.1fp" % diff_p


def confirm_level(level, price: float, atr_val: Optional[float],
                  structure_label: str, momentum_label: str,
                  present_in_1y: bool, present_in_2y: bool,
                  min_touches: int) -> dict:
    """Seviyeyi SAYILABİLİR maddelerle teyit eder — iddia değil, çetele.

    'Birden fazla göstergeyle doğrulandı' ifadesi ancak böyle denetlenebilir olur.
    """
    yon = "destek" if level.hi < price else "direnç"
    trend_ok = (structure_label == OLUMLU and yon == "destek") or \
               (structure_label == OLUMSUZ and yon == "direnç")
    mom_ok = (momentum_label == OLUMLU and yon == "destek") or \
             (momentum_label == OLUMSUZ and yon == "direnç")
    maddeler = [
        ("%d+ dokunuş" % min_touches, level.touches >= min_touches,
         "%d dokunuş" % level.touches),
        ("karma (kutup değişimi)", level.kind == "karma", level.kind),
        ("1y+2y pencerede", bool(present_in_1y and present_in_2y),
         "1y=%s 2y=%s" % (present_in_1y, present_in_2y)),
        ("trend uyumlu", trend_ok, structure_label),
        ("momentum uyumlu", mom_ok, momentum_label),
    ]
    return {"teyit_sayisi": sum(1 for _, ok, _ in maddeler if ok),
            "toplam": len(maddeler), "yon": yon, "maddeler": maddeler}


def bonferroni_note(n_tests: int) -> str:
    """Çoklu test uyarısı — 30+ karşılaştırmada biri şansa bağlı iyi görünür."""
    return ("%d karşılaştırma yapıldı; en iyi görünen sonucun şansa bağlı olma olasılığı "
            "yüksektir. Tek tek 'en iyi' satıra bakmayın." % n_tests)


# ============================================================================
# Doğrulama harness'i — sunumdan ÖNCE inşa edilir
#
# Amaç: seviyelerin ve gösterge etiketlerinin gerçekten yön bilgisi taşıyıp taşımadığını
# ÖLÇMEK. Ölçüm sonucu, raporun ne kadar iddialı konuşabileceğini belirler — tersi değil.
# ============================================================================
def _series(bars: Sequence) -> tuple:
    return ([b["date"] for b in bars], [b["h"] for b in bars],
            [b["l"] for b in bars], [b["c"] for b in bars])


def walk_forward_level_signals(bars: Sequence, cfg: dict) -> dict:
    """Yürüyen-ileri seviye kurulumu → 'desteğe/dirence yakın' sinyal günleri.

    LOOK-AHEAD KORUMASI: t anında yalnız `confirm_idx <= t` olan pivotlar kullanılır —
    bir pivot k bar sonra bilinebilir. Bu gecikmeye uyulmazsa tüm ölçüm geçersizdir.
    Seviyeler her `yeniden_hesap_bar` barda bir yeniden kurulur (seviyeler yavaş hareket
    eder; her gün kurmak O(n²) maliyet için sıfır bilgi kazancı demek).
    """
    ch = cfg["chart"]
    pv, an, th = ch["pivot"], ch["analiz"], ch["gostergeler"]["thresholds"]
    dates, highs, lows, closes = _series(bars)
    n = len(closes)
    k = int(pv["lookback_bar"])
    win = int(an["pencere_gun"])
    step = int(ch["dogrulama"]["yeniden_hesap_bar"])
    yakin = float(th["seviye_yakin_atr"])
    atr_vals = atr(highs, lows, closes, int(ch["gostergeler"]["atr_window"]))

    dest_idx, dir_idx = [], []
    levels_cache = []
    for t in range(win, n):
        if (t - win) % step == 0 or not levels_cache:
            lo = max(0, t - win)
            seg_p = find_pivots(highs[lo:t + 1], lows[lo:t + 1], dates[lo:t + 1], k)
            # confirm gecikmesi: yalnız t'de BİLİNEBİLİR pivotlar
            seg_p = [p for p in seg_p if p.confirm_idx <= (t - lo)]
            a = atr_vals[t]
            tol = max((a / closes[t] * 100.0) * float(pv["kume_atr_carpani"]),
                      float(pv["min_tolerans_pct"])) if a and closes[t] else \
                float(pv["min_tolerans_pct"])
            levels_cache = build_levels(cluster_pivots(seg_p, tol), dates[t],
                                        float(pv["yaricil_omur_gun"]),
                                        int(pv["min_dokunus"]),
                                        float(pv["karma_seviye_carpani"]))
        a = atr_vals[t]
        if not a or not levels_cache:
            continue
        near = nearest_levels(levels_cache, closes[t], 1)
        if near["destekler"]:
            if (closes[t] - near["destekler"][0].price) / a <= yakin:
                dest_idx.append(t)
        if near["direncler"]:
            if (near["direncler"][0].price - closes[t]) / a <= yakin:
                dir_idx.append(t)
    return {"destege_yakin": dest_idx, "dirence_yakin": dir_idx, "n_bar": n}


def indicator_signal_days(bars: Sequence, cfg: dict) -> dict:
    """Her gösterge etiketi için sinyal günleri (saf hesap, look-ahead yok)."""
    ch = cfg["chart"]
    g, th = ch["gostergeler"], ch["gostergeler"]["thresholds"]
    dates, highs, lows, closes = _series(bars)
    r = rsi(closes, int(g["rsi_window"]))
    bb = bollinger(closes, int(g["bollinger_window"]), float(g["bollinger_k"]))
    out = {"rsi_asiri_satim": [], "rsi_asiri_alim": [],
           "bollinger_alt": [], "bollinger_ust": []}
    for i in range(len(closes)):
        lab = label_rsi(r[i], float(th["rsi_asiri_alim"]), float(th["rsi_asiri_satim"]))
        if lab == OLUMLU:
            out["rsi_asiri_satim"].append(i)
        elif lab == OLUMSUZ:
            out["rsi_asiri_alim"].append(i)
        blab = label_bollinger(bb[i][3], float(th["bollinger_ust_pctb"]),
                               float(th["bollinger_alt_pctb"]))
        if blab == OLUMLU:
            out["bollinger_alt"].append(i)
        elif blab == OLUMSUZ:
            out["bollinger_ust"].append(i)
    return out


def measure_edge(dates: Sequence[str], closes: Sequence[float], signal_idx: Sequence[int],
                 horizon: int, weak_n: int, min_diff_p: float) -> dict:
    """Bir sinyal kümesinin taban çizgisine göre ölçülen farkı.

    Taban = KOŞULSUZ tüm günler, aynı örtüşmeyen pencere yöntemiyle. Bilgi mutlak
    medyanda değil, tabandan FARKTA (backtest._fmt_stat konvansiyonu).
    """
    from . import backtest as bt
    sig = bt.dist_stats(bt.forward_returns_nonoverlap(dates, closes, signal_idx, horizon),
                        weak_n)
    base = bt.dist_stats(
        bt.forward_returns_nonoverlap(dates, closes, list(range(len(closes))), horizon),
        weak_n)
    diff = (sig["medyan"] - base["medyan"]) if (sig.get("n") and base.get("n")) else None
    return {"stat": sig, "baseline": base, "fark": diff,
            "n": sig.get("n", 0),
            "hukum": edge_verdict(diff, sig.get("n", 0), weak_n, min_diff_p),
            "etkin_donem": bt.effective_periods(len(signal_idx), horizon)}


def validate(cfg: dict) -> dict:
    """Tam doğrulama: seviyeler + göstergeler, in-sample ve OOS ayrı.

    `reports/grafik_dogrulama.md` + `data/grafik_edge.json` yazar. Yavaş (yürüyen-ileri)
    olduğu için daily_job'a BAĞLANMAZ; elle veya workflow_dispatch ile çalışır.
    """
    import json

    from . import db, util
    from . import ohlc_hist

    ch = cfg["chart"]
    bt_cfg = cfg["backtest"]
    weak_n = int(bt_cfg["weak_n_threshold"])
    min_diff = float(ch["dogrulama"]["min_anlamli_fark_puan"])
    horizons = bt_cfg["horizons_days"]
    oos = bt_cfg["oos_split"]

    con = db.connect(cfg)
    try:
        bars = ohlc_hist.load_ohlc(con, ch["ohlc"]["symbols"]["ons"])
    finally:
        con.close()
    if len(bars) < int(ch["analiz"]["pencere_gun"]) + 60:
        return {"hata": "yetersiz OHLC (%d bar)" % len(bars)}

    bars = ohlc_hist.drop_unclosed_bar(bars, util.utcnow().strftime("%Y-%m-%d"))
    dates, highs, lows, closes = _series(bars)

    lvl = walk_forward_level_signals(bars, cfg)
    ind = indicator_signal_days(bars, cfg)
    gruplar = {"Desteğe yakın": lvl["destege_yakin"],
               "Dirence yakın": lvl["dirence_yakin"]}
    gruplar.update({"RSI aşırı satım": ind["rsi_asiri_satim"],
                    "RSI aşırı alım": ind["rsi_asiri_alim"],
                    "Bollinger alt": ind["bollinger_alt"],
                    "Bollinger üst": ind["bollinger_ust"]})

    oos_start = next((i for i, d in enumerate(dates) if d >= oos), len(dates))
    sonuc, n_test = {}, 0
    for ad, idx in gruplar.items():
        sonuc[ad] = {}
        for hname, h in horizons.items():
            tum = measure_edge(dates, closes, idx, int(h), weak_n, min_diff)
            ins = measure_edge(dates, closes, [i for i in idx if i < oos_start],
                               int(h), weak_n, min_diff)
            oo = measure_edge(dates, closes, [i for i in idx if i >= oos_start],
                              int(h), weak_n, min_diff)
            sonuc[ad][hname] = {"tum": tum, "in_sample": ins, "oos": oo}
            n_test += 1

    # --- markdown rapor ---
    from . import backtest as bt
    L = ["# Grafik Doğrulama Raporu", "",
         "Seri: **%s** · %d bar (%s → %s)" % (ch["ohlc"]["symbols"]["ons"], len(bars),
                                              dates[0], dates[-1]), "",
         "> **Seviyeler geometridir; 'fark' sütunu ölçümdür.** Fark ≈0 ise seviyenin yön",
         "> bilgisi yoktur — kademe/stop planlaması için yine kullanılabilir (mekanik kural),",
         "> **yön iddiası için kullanılamaz.**", "",
         "> " + bonferroni_note(n_test * 3), "",
         "> Hacim ağırlıklandırması KULLANILMADI (GC=F hacmi ön-vade kontrat hacmi;",
         "> TRY=X hacmi 0). MACD dışarıda (50/200 GMA ile eşdoğrusal).", ""]
    for ad, per_h in sonuc.items():
        L.append("## %s" % ad)
        L.append("")
        for hname, d in per_h.items():
            t = d["tum"]
            L.append("- **%s** (tüm dönem): %s → _%s_ · etkin dönem ~%d"
                     % (hname, bt._fmt_stat(t["stat"], t["baseline"]),
                        t["hukum"], t["etkin_donem"]))
            L.append("  - in-sample: _%s_ · OOS (%s+): _%s_"
                     % (d["in_sample"]["hukum"], oos, d["oos"]["hukum"]))
        L.append("")
    L.append("---")
    L.append("_Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir._")

    out_path = util.abspath(cfg["paths"]["reports_dir"]) / ch["dogrulama"]["rapor_dosyasi"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(L), encoding="utf-8")

    cache = {ad: {h: {"fark": d["tum"]["fark"], "n": d["tum"]["n"],
                      "hukum": d["tum"]["hukum"]}
                  for h, d in per_h.items()} for ad, per_h in sonuc.items()}
    cache_path = util.abspath(ch["dogrulama"]["edge_cache_file"])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"rapor": str(out_path), "cache": str(cache_path),
            "bar": len(bars), "karsilastirma": n_test * 3}


# ============================================================================
# Sunum — build_chart / format_chart_md
#
# ÖLÇÜM SONUCU (validate, 21 Tem 2026, 2649 bar): destek/dirence yakınlık taban çizgisine
# göre 1 ay ufkunda −0.2p / −0.7p → **kenar yok**; 3-6 ay ufuklarında N=6-13 → ölçüm
# yetersiz. Göstergelerin "zayıf kanıt" çıkan satırları ufuklar arasında çelişiyor
# (54 karşılaştırma). Dolayısıyla bu bölüm seviyeleri **planlama geometrisi** olarak
# sunar, yön iddiası olarak DEĞİL. Dil bu ölçüme göre seçilmiştir.
# ============================================================================
def _edge_cache(cfg: dict) -> dict:
    import json

    from . import util
    try:
        p = util.abspath(cfg["chart"]["dogrulama"]["edge_cache_file"])
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("edge cache okunamadı: %s", e)
    return {}


def build_chart(cfg: dict, refresh: bool = False) -> dict:
    """Grafik yorumu verisi. refresh=False → yalnız DB (bot/rapor yolunda ağ beklemesin)."""
    from . import db, ohlc_hist, util

    ch = cfg["chart"]
    if not ch.get("enabled", True):
        return {"yok": "kapalı"}
    if refresh:
        try:
            ohlc_hist.update_ohlc_daily(cfg)
        except Exception as e:
            log.warning("ohlc guncelleme hata: %s", e)

    pv, an, g = ch["pivot"], ch["analiz"], ch["gostergeler"]
    th = g["thresholds"]
    con = db.connect(cfg)
    try:
        bars = ohlc_hist.load_ohlc(con, ch["ohlc"]["symbols"]["ons"])
        kur_bars = ohlc_hist.load_ohlc(con, ch["ohlc"]["symbols"]["kur"])
    finally:
        con.close()
    if ch["ohlc"].get("son_bar_kapanmamis_atla", True):
        today = util.utcnow().strftime("%Y-%m-%d")
        bars = ohlc_hist.drop_unclosed_bar(bars, today)
        kur_bars = ohlc_hist.drop_unclosed_bar(kur_bars, today)
    if len(bars) < 60:
        return {"yok": "yetersiz OHLC (%d bar)" % len(bars)}

    win = int(an["pencere_gun"])
    bars2 = bars[-win:]
    dates, highs, lows, closes = _series(bars2)
    spot = closes[-1]
    k = int(pv["lookback_bar"])

    atr_all = atr([b["h"] for b in bars], [b["l"] for b in bars],
                  [b["c"] for b in bars], int(g["atr_window"]))
    atr_val = atr_all[-1]
    atr_pct = (atr_val / spot * 100.0) if (atr_val and spot) else None

    tol = max((atr_pct or 0) * float(pv["kume_atr_carpani"]),
              float(pv["min_tolerans_pct"]))
    piv2 = find_pivots(highs, lows, dates, k)
    lv2 = build_levels(cluster_pivots(piv2, tol), dates[-1], float(pv["yaricil_omur_gun"]),
                       int(pv["min_dokunus"]), float(pv["karma_seviye_carpani"]))
    # ikincil pencere: aynı seviye 1y'de de görünüyor mu (parametre kararlılığı)
    w1 = int(an["ikincil_pencere_gun"])
    b1 = bars[-w1:]
    d1, h1, l1, c1 = _series(b1)
    lv1 = build_levels(cluster_pivots(find_pivots(h1, l1, d1, k), tol), d1[-1],
                       float(pv["yaricil_omur_gun"]), int(pv["min_dokunus"]),
                       float(pv["karma_seviye_carpani"]))

    def _in_1y(L):
        return any(abs(x.price - L.price) / L.price * 100.0 <= tol for x in lv1 if L.price)

    near = nearest_levels(lv2, spot, int(pv["gosterilecek_seviye"]))

    # göstergeler
    r = rsi(closes, int(g["rsi_window"]))
    bb = bollinger(closes, int(g["bollinger_window"]), float(g["bollinger_k"]))
    struct = swing_structure(piv2, int(g["yapisal_swing_sayisi"]))
    lab_struct = label_trend_structure(struct["hh"], struct["hl"], struct["lh"], struct["ll"])
    lab_rsi = label_rsi(r[-1], float(th["rsi_asiri_alim"]), float(th["rsi_asiri_satim"]))
    lab_bb = label_bollinger(bb[-1][3], float(th["bollinger_ust_pctb"]),
                             float(th["bollinger_alt_pctb"]))

    # oynaklık rejimi (yönsüz — oylamaya girmez)
    from . import backtest as bt
    hist_atr_pct = [a / c * 100.0 for a, c in zip(atr_all, [b["c"] for b in bars])
                    if a and c]
    srt = sorted(hist_atr_pct)
    p33 = bt._pct(srt, float(th["atr_rejim_p_dusuk"]) / 100.0) if srt else 0.0
    p66 = bt._pct(srt, float(th["atr_rejim_p_yuksek"]) / 100.0) if srt else 0.0
    vol_rejim = label_vol_regime(atr_pct, p33, p66)

    ext = extremes([b["h"] for b in bars], [b["l"] for b in bars],
                   [b["date"] for b in bars],
                   {"1y": w1, "2y": win, "tum": 0}, spot=spot)
    zirve_yakin = False
    if ext.get("tum") and atr_val:
        zirve = ext["tum"]["zirve"][1]
        zirve_yakin = (zirve - spot) <= float(th["zirve_yakin_atr"]) * atr_val

    # seviye teyitleri
    momentum = lab_rsi if lab_rsi != NOTR else lab_bb
    teyitler = {}
    for grup in ("destekler", "direncler"):
        for L in near[grup]:
            teyitler[L.price] = confirm_level(
                L, spot, atr_val, lab_struct, momentum,
                _in_1y(L), True, int(pv["min_dokunus"]))

    usdtry = kur_bars[-1]["c"] if kur_bars else None

    # grafik uzlaşısı — ana panele değil, KENDİ içinde (fiyat türevi göstergeler
    # korelasyonlu; ana panele 4 oy girerse panel momentum göstergesine dönüşür)
    from .indicators import Signal, consensus
    sigs = [Signal("Ons trend yapısı", lab_struct, str(struct["son_tepeler"])),
            Signal("Ons RSI(14)", lab_rsi, "%.1f" % r[-1] if r[-1] else "veri yok"),
            Signal("Ons Bollinger %B", lab_bb,
                   "%.2f" % bb[-1][3] if bb[-1][3] is not None else "veri yok")]
    if near["destekler"] and atr_val:
        m = (spot - near["destekler"][0].price) / atr_val
        sigs.append(Signal("Desteğe yakınlık",
                           label_level_proximity(m, float(th["seviye_yakin_atr"]), "destek"),
                           "%.1f ATR" % m))
    cons = consensus(sigs)

    return {"sembol": ch["ohlc"]["symbols"]["ons"], "son_bar": dates[-1],
            "spot": spot, "atr": atr_val, "atr_pct": atr_pct, "vol_rejim": vol_rejim,
            "bar_sayisi": len(bars), "seviyeler": near, "teyitler": teyitler,
            "ekstremler": ext, "zirve_yakin": zirve_yakin,
            "rsi": r[-1], "pctb": bb[-1][3], "yapi": struct,
            "etiketler": {"yapi": lab_struct, "rsi": lab_rsi, "bollinger": lab_bb},
            "sinyaller": sigs, "uzlasi": cons, "usdtry": usdtry,
            "edge": _edge_cache(cfg), "troy": cfg["instruments"]["troy_ounce_gram"]}


_EMOJI = {OLUMLU: "🟢", NOTR: "⚪", OLUMSUZ: "🔴", YOK: "➖"}


def _tl(ons_price: float, usdtry: Optional[float], troy: float) -> str:
    """Ons seviyesinin BUGÜNKÜ kurla gram TL izdüşümü (kur yazılır)."""
    if not usdtry:
        return ""
    from . import calc
    return " · TL izdüşümü: kur %.2f iken ~%s ₺/gram" % (
        usdtry, format(calc.theoretical_gram(ons_price, usdtry, troy), ",.0f"))


def _edge_line(edge: dict, ad: str, ufuk: str = "1ay") -> str:
    d = (edge.get(ad) or {}).get(ufuk)
    if not d:
        return ""
    f = d.get("fark")
    if f is None:
        return " · ölçüm yok"
    return " · ölçülen %s farkı **%+.1fp** (N=%d) → _%s_" % (ufuk, f, d.get("n", 0),
                                                             d.get("hukum", ""))


def format_chart_md(result: dict) -> str:
    """Rapora eklenecek markdown blok.

    Telegram `parse_mode=None` ile gidiyor ve `_md_to_plain()` kalın/başlık işaretlerini
    siliyor; geniş tablolar boru çorbasına döndüğü için MADDE İŞARETLİ yazılır.
    """
    if not result or result.get("yok"):
        return ""
    L = ["## Grafik Yorumu (ons USD · %s günlük)" % result["sembol"], ""]
    L.append("- Kapanış **%s $** (%s · son KAPANMIŞ bar) · ATR(14) %s $ (%%%.2f) · "
             "oynaklık %s" % (format(result["spot"], ",.0f"), result["son_bar"],
                              format(result["atr"] or 0, ",.0f"),
                              result["atr_pct"] or 0, result["vol_rejim"]))
    ext = result.get("ekstremler", {})
    for ad in ("1y", "2y", "tum"):
        e = ext.get(ad)
        if e:
            L.append("- %s zirve %s (%s) · dip %s (%s) · zirveden %%%.1f"
                     % (ad, format(e["zirve"][1], ",.0f"), e["zirve"][0],
                        format(e["dip"][1], ",.0f"), e["dip"][0],
                        e["zirveden_uzaklik_pct"]))
    if result.get("zirve_yakin"):
        L.append("- ⚠️ **Fiyat tüm zamanların zirvesinde — ÜSTTE DİRENÇ YOKTUR** "
                 "(o bölgede hiç işlem geçmemiştir; oradaki her 'seviye' uydurmadır).")
    L.append("")

    troy, usdtry, edge = result["troy"], result.get("usdtry"), result.get("edge", {})
    for baslik, grup, ad in (("Dirençler (üstte)", "direncler", "Dirence yakın"),
                             ("Destekler (altta)", "destekler", "Desteğe yakın")):
        L.append("### %s" % baslik)
        lst = result["seviyeler"].get(grup) or []
        if not lst:
            L.append("- yok")
        for lv in lst:
            t = result["teyitler"].get(lv.price, {})
            mesafe = abs(lv.price - result["spot"]) / result["atr"] if result["atr"] else 0
            L.append("- **%s–%s $** bandı · %d dokunuş · son %s · skor %.1f · "
                     "**teyit %d/%d**"
                     % (format(lv.lo, ",.0f"), format(lv.hi, ",.0f"), lv.touches,
                        lv.last_date, lv.score, t.get("teyit_sayisi", 0),
                        t.get("toplam", 5)))
            L.append("  - mesafe: %.1f ATR (%%%.1f)%s"
                     % (mesafe, abs(lv.price / result["spot"] - 1) * 100,
                        _tl(lv.price, usdtry, troy)))
            if t.get("maddeler"):
                L.append("  - " + " ".join(("✓" if ok else "✗") + n
                                           for n, ok, _ in t["maddeler"]))
        L.append("- _%s:_%s" % (ad, _edge_line(edge, ad) or " ölçüm yok"))
        L.append("")

    L.append("### Göstergeler (çapraz doğrulama)")
    et = result["etiketler"]
    y = result["yapi"]
    L.append("- Trend yapısı: %s %s — son tepeler %s, son dipler %s"
             % (_EMOJI.get(et["yapi"], ""), et["yapi"],
                [round(x) for x in y["son_tepeler"]], [round(x) for x in y["son_dipler"]]))
    L.append("- RSI(14) %s: %s %s%s"
             % ("%.1f" % result["rsi"] if result["rsi"] else "—",
                _EMOJI.get(et["rsi"], ""), et["rsi"],
                _edge_line(edge, "RSI aşırı satım" if et["rsi"] == OLUMLU
                           else "RSI aşırı alım")))
    L.append("- Bollinger %%B %s: %s %s%s"
             % ("%.2f" % result["pctb"] if result["pctb"] is not None else "—",
                _EMOJI.get(et["bollinger"], ""), et["bollinger"],
                _edge_line(edge, "Bollinger alt" if et["bollinger"] == OLUMLU
                           else "Bollinger üst")))
    c = result["uzlasi"]
    L.append("- **Grafik uzlaşısı: %s %s — skor %+d/%d**"
             % (_EMOJI.get(c["yon"], ""), c["yon"], c["score"], c["n"]))
    L.append("")
    L.append("> Seviyeler **geometridir, ölçüm değildir.** Ölçüm satırları taban çizgisi")
    L.append("> (tüm günler) karşısındaki örtüşmeyen-pencere farkıdır; ≈0 ise yön bilgisi")
    L.append("> yoktur — seviye yine kademe/stop planlaması için kullanılabilir, **yön**")
    L.append("> **iddiası için kullanılamaz.** Hacim ağırlıklandırması YOK (GC=F hacmi")
    L.append("> ön-vade kontrat hacmi, TRY=X hacmi 0). TL seviyesi türetilmez — ons")
    L.append("> seviyesinin bugünkü kurla izdüşümüdür.")
    return "\n".join(L)


if __name__ == "__main__":
    import sys as _sys

    from . import logging_setup, util
    util.load_env()
    _cfg = util.load_config()
    logging_setup.setup("chart", _cfg)
    if len(_sys.argv) > 1 and _sys.argv[1] == "validate":
        print(validate(_cfg))
    else:
        print(format_chart_md(build_chart(_cfg)))
