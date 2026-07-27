"""Bölüm 8f — Görsel grafik: metnin söylediğini GÖSTER.

Metin rapor "neyi" ve "niçin"i anlatır; grafik "nerede duruyoruz"u tek bakışta
verir. İkisi birbirinin yerine geçmez, bu yüzden metin `/grafik` KALDI.

## Tasarım kısıtları (uydurma değil, veriden gelen)

1. **Gram TL için mum grafiği YOK.** `db.py` şema kuralı: gram TL için OHLC
   türetilmez, çünkü `high_gram ≠ high_ons × high_usdtry` — günün en yüksek onsu
   ile en yüksek kuru aynı ana denk gelmez, çarpım hayali fitiller üretir. Gram
   paneli bu yüzden **kapanış çizgisi**; mum çizmek veriyi güzelleştirip
   yalan söylemek olurdu.
2. **Destek/direnç ONS üzerinde.** Seviyeler `chart.build_levels` ile GC=F
   gerçek OHLC'sinden çıkarılıyor; gram TL'ye taşınmıyor.
3. **Hacim çizilmiyor.** `chart.py` gerekçesi: GC=F hacmi ön-vade kontrat
   hacmidir ve vade geçişlerinde süreksizdir (2016'da 143 → bugün 44 361);
   TRY=X hacmi hep 0.
4. **Seviye kalınlığı skorla değişmez.** `score_level` yalnız gösterim
   sıralaması içindir; kalın çizgi "daha güçlü seviye" izlenimi verirdi ve
   ölçüm bunu desteklemiyor (`chart.validate`: "kenar yok").

Headless çalışır (Agg backend) — GitHub Actions'ta ekran yok.
matplotlib **lazy import** edilir: `archive.yml` onu kurmuyor ve bu modülün
yokluğu diğer akışları düşürmemeli.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import util

log = logging.getLogger("grafik_ciz")

# Yalnız SON ÇARE varsayılan: gerçek yol `config.yaml chart.gorsel.cikti`.
# Burada sabit bir "data/grafik.png" vardı ve config'teki aynı anahtar hiç
# okunmuyordu — yani config'i değiştirmek sessizce hiçbir şey yapmıyordu
# (aynı yolun iki kaynağı). Kural: config varsa config kazanır.
CIKTI_VARSAYILAN = "data/grafik.png"

# Renkler: açık zeminde okunur, Telegram'ın hem açık hem koyu temasında çalışır
C_FIYAT = "#1a1a1a"
C_GMA50 = "#e67e22"
C_GMA200 = "#2980b9"
C_DESTEK = "#27ae60"
C_DIRENC = "#c0392b"
C_ONS = "#b8860b"
C_KUR = "#7f8c8d"
C_IZGARA = "#dddddd"


def _sma(seri, pencere):
    """Basit hareketli ortalama; yetersiz baştaki elemanlar None."""
    out = [None] * len(seri)
    for i in range(pencere - 1, len(seri)):
        out[i] = sum(seri[i - pencere + 1:i + 1]) / pencere
    return out


def _seyrek_etiket(ax, tarihler, adet=6):
    """X ekseninde `adet` kadar tarih etiketi — kalabalık eksen okunmaz."""
    n = len(tarihler)
    if n == 0:
        return
    adim = max(1, n // adet)
    yerler = list(range(0, n, adim))
    ax.set_xticks(yerler)
    ax.set_xticklabels([tarihler[i][:7] for i in yerler], fontsize=8)


def ciz(cfg: dict, cikti_yolu: Optional[str] = None) -> Optional[str]:
    """Grafiği üretir, PNG yolunu döner. matplotlib yoksa None (sessiz düşer)."""
    try:
        import matplotlib
        matplotlib.use("Agg")                    # headless — Actions'ta ekran yok
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except ImportError:
        log.warning("matplotlib kurulu degil — gorsel grafik atlandi")
        return None

    from . import chart, db, ohlc_hist

    ch = cfg["chart"]
    g = ch["gostergeler"]
    con = db.connect(cfg)
    try:
        ons_bars = ohlc_hist.load_ohlc(con, ch["ohlc"]["symbols"]["ons"])
        hist = con.execute(
            "SELECT date, gram_teorik, ons_usd, usdtry FROM history_daily "
            "WHERE gram_teorik IS NOT NULL ORDER BY date").fetchall()
    finally:
        con.close()
    if ch["ohlc"].get("son_bar_kapanmamis_atla", True):
        ons_bars = ohlc_hist.drop_unclosed_bar(
            ons_bars, util.utcnow().strftime("%Y-%m-%d"))
    if len(ons_bars) < 60 or len(hist) < 60:
        log.warning("yetersiz veri — grafik cizilmedi")
        return None

    win = int(ch["analiz"]["pencere_gun"])
    ons2 = ons_bars[-win:]
    o_tarih = [b["date"] for b in ons2]
    o_h = [b["h"] for b in ons2]
    o_l = [b["l"] for b in ons2]
    o_o = [b["o"] for b in ons2]
    o_c = [b["c"] for b in ons2]

    h2 = hist[-win:]
    g_tarih = [r["date"] for r in h2]
    g_gram = [r["gram_teorik"] for r in h2]
    g_ons = [r["ons_usd"] for r in h2]
    g_kur = [r["usdtry"] for r in h2]

    # Seviyeler: mevcut motordan (yeniden hesaplama YOK — tek kaynak)
    try:
        c = chart.build_chart(cfg, refresh=False)
        seviyeler = c.get("seviyeler", {"destekler": [], "direncler": []})
        spot = c.get("spot")
    except Exception as e:
        log.warning("seviyeler alinamadi: %s", e)
        seviyeler, spot = {"destekler": [], "direncler": []}, o_c[-1]

    fig, axes = plt.subplots(
        4, 1, figsize=(10, 13), sharex=False,
        gridspec_kw={"height_ratios": [3.2, 2.2, 2.0, 1.1], "hspace": 0.38,
                     # top/bottom açıkça verilir: varsayılan (0.9) 13 inçlik bir
                     # figürde başlık ile ilk panel arasında dev bir boşluk
                     # bırakıyor ve bbox_inches="tight" bunu kırpmıyor.
                     # right: son fiyat etiketi ("6,177₺") panelin sağına
                     # taşıyor, yer bırakılmazsa kırpılır.
                     "top": 0.955, "bottom": 0.055, "left": 0.075, "right": 0.925})
    fig.patch.set_facecolor("white")

    # ---------- Panel 1: Ons USD mum + destek/direnç ----------
    ax = axes[0]
    for i in range(len(ons2)):
        yukseldi = o_c[i] >= o_o[i]
        renk = "#26a69a" if yukseldi else "#ef5350"
        ax.plot([i, i], [o_l[i], o_h[i]], color=renk, linewidth=0.6, zorder=2)
        alt, ust = min(o_o[i], o_c[i]), max(o_o[i], o_c[i])
        ax.add_patch(Rectangle((i - 0.35, alt), 0.7, max(ust - alt, 1e-9),
                               facecolor=renk, edgecolor=renk, linewidth=0.4, zorder=3))
    for pencere, renk in ((50, C_GMA50), (200, C_GMA200)):
        m = _sma(o_c, pencere)
        ax.plot(range(len(m)), m, color=renk, linewidth=1.3,
                label=f"{pencere} GMA", zorder=4)
    # Seviye BANTLARI (tek çizgi değil): bir seviye nokta değil aralıktır
    for grup, renk, ad in (("destekler", C_DESTEK, "destek"),
                           ("direncler", C_DIRENC, "direnç")):
        for j, L in enumerate(seviyeler.get(grup, [])):
            ax.axhspan(L.lo, L.hi, color=renk, alpha=0.13, zorder=1)
            ax.axhline(L.price, color=renk, linewidth=0.9, linestyle="--",
                       alpha=0.75, zorder=5,
                       label=f"{ad} ({L.touches} dokunuş)" if j == 0 else None)
    if spot:
        ax.axhline(spot, color=C_FIYAT, linewidth=1.0, alpha=0.5, zorder=6)
        ax.annotate(f"{spot:,.0f}$", xy=(len(ons2) - 1, spot),
                    xytext=(6, 0), textcoords="offset points",
                    fontsize=9, va="center", fontweight="bold")
    ax.set_title(f"Ons USD ({ch['ohlc']['symbols']['ons']}) — {len(ons2)} bar · "
                 "destek/direnç bantları", fontsize=11, fontweight="bold", loc="left")
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
    ax.grid(True, color=C_IZGARA, linewidth=0.5, alpha=0.7)
    ax.set_ylabel("USD/ons", fontsize=9)
    _seyrek_etiket(ax, o_tarih)

    # ---------- Panel 2: Gram TL — ÇİZGİ (mum değil, kural gereği) ----------
    ax = axes[1]
    ax.plot(range(len(g_gram)), g_gram, color=C_FIYAT, linewidth=1.4,
            label="gram TL (teorik has)")
    for pencere, renk in ((50, C_GMA50), (200, C_GMA200)):
        m = _sma(g_gram, pencere)
        ax.plot(range(len(m)), m, color=renk, linewidth=1.2, label=f"{pencere} GMA")
    ax.annotate(f"{g_gram[-1]:,.0f}₺", xy=(len(g_gram) - 1, g_gram[-1]),
                xytext=(6, 0), textcoords="offset points",
                fontsize=9, va="center", fontweight="bold")
    ax.set_title("Gram TL — kapanış çizgisi "
                 "(gram için OHLC türetilmez: high_ons × high_kur aynı ana ait değil)",
                 fontsize=10, fontweight="bold", loc="left")
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
    ax.grid(True, color=C_IZGARA, linewidth=0.5, alpha=0.7)
    ax.set_ylabel("TL/gram", fontsize=9)
    _seyrek_etiket(ax, g_tarih)

    # ---------- Panel 3: İKİ MOTOR — hareketi hangisi çekiyor? ----------
    # TL altının iki bacağı var ve ölçüm taktik kazanç varyansının ~%91'inin
    # TL bacağında olduğunu söylüyor (ADR #007). Bu panel o soruyu görselleştirir.
    ax = axes[2]
    tab_o, tab_k = g_ons[0], g_kur[0]
    ax.plot(range(len(g_ons)), [x / tab_o * 100 for x in g_ons],
            color=C_ONS, linewidth=1.5, label="Ons USD")
    ax.plot(range(len(g_kur)), [x / tab_k * 100 for x in g_kur],
            color=C_KUR, linewidth=1.5, label="USD/TRY")
    ax.plot(range(len(g_gram)), [x / g_gram[0] * 100 for x in g_gram],
            color=C_FIYAT, linewidth=1.8, label="Gram TL (= ons × kur)")
    ax.axhline(100, color="#999999", linewidth=0.8, linestyle=":")
    o_chg = (g_ons[-1] / tab_o - 1) * 100
    k_chg = (g_kur[-1] / tab_k - 1) * 100
    ax.set_title(f"İki motor — dönem başına göre  ·  ons {o_chg:+.0f}%  ·  "
                 f"kur {k_chg:+.0f}%", fontsize=10, fontweight="bold", loc="left")
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
    ax.grid(True, color=C_IZGARA, linewidth=0.5, alpha=0.7)
    ax.set_ylabel("endeks (başlangıç=100)", fontsize=9)
    _seyrek_etiket(ax, g_tarih)

    # ---------- Panel 4: RSI(14) ----------
    ax = axes[3]
    r = chart.rsi(o_c, int(g["rsi_window"]))
    th = g["thresholds"]
    ax.plot(range(len(r)), r, color="#8e44ad", linewidth=1.2)
    ax.axhline(float(th["rsi_asiri_alim"]), color=C_DIRENC, linewidth=0.8,
               linestyle="--", alpha=0.8)
    ax.axhline(float(th["rsi_asiri_satim"]), color=C_DESTEK, linewidth=0.8,
               linestyle="--", alpha=0.8)
    ax.set_ylim(0, 100)
    ax.set_title(f"Ons RSI(14) — son {r[-1]:.0f}" if r[-1] else "Ons RSI(14)",
                 fontsize=10, fontweight="bold", loc="left")
    ax.grid(True, color=C_IZGARA, linewidth=0.5, alpha=0.7)
    _seyrek_etiket(ax, o_tarih)

    yerel = util.to_local(util.utcnow(), cfg.get("timezone_offset_hours", 3))
    fig.suptitle(f"Altın Takip — {yerel.strftime('%d.%m.%Y %H:%M')} (TR)",
                 fontsize=13, fontweight="bold", y=0.985)
    fig.text(0.5, 0.008,
             "Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir. "
             "Seviyeler planlama geometrisidir — ölçülen yön kenarı YOKTUR.",
             ha="center", fontsize=8, color="#666666")

    yol = util.abspath(cikti_yolu
                       or cfg.get("chart", {}).get("gorsel", {}).get("cikti")
                       or CIKTI_VARSAYILAN)
    yol.parent.mkdir(parents=True, exist_ok=True)
    # bbox_inches="tight" YOK: yukarıdaki subplots_adjust yerleşimi zaten
    # belirliyor; "tight" sağdaki fiyat etiketlerini de kırpıyordu.
    fig.savefig(str(yol), dpi=110, facecolor="white")
    plt.close(fig)
    log.info("grafik cizildi: %s", yol)
    return str(yol)


if __name__ == "__main__":
    util.load_env()
    print(ciz(util.load_config()) or "cizilemedi")
