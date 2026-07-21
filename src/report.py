"""Gün sonu markdown raporu: fiyat özeti + dekompozisyon + prim/makas + veri kalitesi.

Rapor hem dosyaya yazılır hem (istenirse) Telegram'a gönderilir.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import calc, db, indicators, util
from . import evds_job

log = logging.getLogger("report")


def weekend_section(con, cfg, days: int = 3) -> list:
    """Son N günde hafta sonu beklenti kaydı varsa 'beklenti vs gerçekleşme' bölümü.

    Veri yoksa boş liste (rapor sessiz kalır — hafta içi yanlışlıkla görünmez).
    """
    from datetime import timedelta
    since = util.iso(util.utcnow() - timedelta(days=days))
    rows = con.execute(
        "SELECT ts_utc,expectation_pct FROM weekend_expectation "
        "WHERE ts_utc>=? ORDER BY ts_utc", (since,)
    ).fetchall()
    if not rows:
        return []                     # SESSİZ
    # gerçekleşen = en yeni GEÇERLİ (hafta içi) prim
    realized = con.execute(
        "SELECT prim_pct FROM prim_history WHERE indicative=0 AND weekend=0 "
        "ORDER BY ts_utc DESC LIMIT 1"
    ).fetchone()
    exp_avg = sum(r["expectation_pct"] for r in rows if r["expectation_pct"] is not None) / len(rows)
    out = ["## Hafta Sonu Beklentisi vs Gerçekleşme", "",
           f"- Hafta sonu ortalama beklenti (donmuş teoriğe göre): **%{exp_avg:+.2f}** "
           f"({len(rows)} nokta)"]
    if realized:
        out.append(f"- Pazartesi gerçekleşen prim: **%{realized['prim_pct']:+.2f}** · "
                   f"fark: **{realized['prim_pct'] - exp_avg:+.2f} puan**")
    else:
        out.append("- _Gerçekleşme için hafta içi geçerli prim henüz yok._")
    out.append("")
    return out


def effective_freq_minutes(cfg) -> float:
    """Beklenen veri sıklığı (dk) — çalışma moduna göre.

    'actions' modunda NOMİNAL cron değil, GitHub'ın kısıtlama sonrası gerçekte teslim
    ettiği GÖZLEMLENEN ritim esas alınır; yoksa sağlıklı sistem arızalı raporlanır.
    'collector' modunda (Oracle 7/24) truncgil poll_seconds geçerlidir.
    """
    if cfg.get("runtime_mode", "actions") == "collector":
        return cfg["sources"]["truncgil"]["poll_seconds"] / 60.0
    a = cfg["alerts"]
    return float(a.get("archive_observed_freq_minutes",
                       a.get("archive_freq_minutes", 15)))


def archive_health(cfg, hours: int = 24) -> dict:
    """Arşiv CSV'lerinden son N saatte başarı oranı + en uzun boşluk (Actions sağlığı).

    Her başarılı arşiv çalışması bir CSV satırı ekler. Boşluk ancak gözlemlenen ritmin
    tolerans katını AŞARSA arıza sayılır — normal cron kısıtlaması arıza değildir.
    """
    import csv
    import glob
    from datetime import timedelta
    files = sorted(glob.glob(str(util.abspath("data/archive") / "*.csv")))
    now = util.utcnow()
    since = now - timedelta(hours=hours)
    ts = []
    for path in files[-2:]:                 # son 2 ay dosyası yeter
        for row in csv.DictReader(open(path, encoding="utf-8")):
            try:
                t = datetime.fromisoformat(row["ts_utc"])
                if t >= since:
                    ts.append(t)
            except (ValueError, KeyError):
                continue
    ts.sort()
    freq = effective_freq_minutes(cfg)
    expected = int(hours * 60 / freq) if freq else 0
    actual = len(ts)
    max_gap_min = 0.0
    if len(ts) >= 2:
        max_gap_min = max((ts[i] - ts[i - 1]).total_seconds() / 60
                          for i in range(1, len(ts)))
    tol = freq * float(cfg["alerts"].get("archive_gap_tolerance_factor", 4.0))
    consec_fail = int(max_gap_min / freq) - 1 if (freq and max_gap_min > tol) else 0
    return {"basari": actual, "beklenen": expected,
            "basari_pct": min(100.0, actual / expected * 100) if expected else 0,
            "en_uzun_bosluk_dk": max_gap_min,
            "tolerans_dk": tol,
            "ardisik_basarisiz": max(0, consec_fail)}


def coverage_report(con, cfg, hours: int = 24) -> dict:
    """Son N saatte veri kapsaması ve en uzun kesinti.

    Beklenen kayıt sayısı çalışma moduna göre (bkz. effective_freq_minutes): Actions
    modunda toplayıcının poll_seconds'ı değil, arşivin gözlemlenen ritmi esastır.
    """
    from datetime import timedelta
    now = util.utcnow()
    since = util.iso(now - timedelta(hours=hours))
    rows = con.execute(
        "SELECT ts_utc FROM prim_history WHERE ts_utc>=? ORDER BY ts_utc", (since,)
    ).fetchall()
    freq_min = effective_freq_minutes(cfg)
    expected = int(hours * 60 / freq_min) if freq_min else 0
    actual = len(rows)
    cov = min(100.0, actual / expected * 100.0) if expected else 0.0
    max_gap_min = 0.0
    if len(rows) >= 2:
        ts = [datetime.fromisoformat(r["ts_utc"]) for r in rows]
        gaps = [(ts[i] - ts[i - 1]).total_seconds() / 60.0 for i in range(1, len(ts))]
        max_gap_min = max(gaps) if gaps else 0.0
    # ilk kayıt now-hours'tan yeniyse, baştaki delik de kesinti
    return {"coverage_pct": cov, "actual": actual, "expected": expected,
            "max_gap_min": max_gap_min}


def _fmt(v, suffix="", nd=2):
    if v is None:
        return "—"
    return f"{v:,.{nd}f}{suffix}"


def _prim_at_or_before(con, ts_iso: str):
    return con.execute(
        "SELECT * FROM prim_history WHERE ts_utc<=? ORDER BY ts_utc DESC LIMIT 1",
        (ts_iso,),
    ).fetchone()


def build_report(cfg: dict) -> str:
    con = db.connect(cfg)
    off = cfg.get("timezone_offset_hours", 3)
    now = util.utcnow()
    local = util.to_local(now, off)
    latest = db.latest_prim(con)

    lines = []
    lines.append(f"# 🥇 Altın Günlük Rapor — {local.strftime('%d.%m.%Y %H:%M')} (TR)")
    lines.append("")

    if latest is None:
        lines.append("_Henüz prim verisi yok. Toplayıcı yeni başlamış olabilir._")
        con.close()
        return "\n".join(lines)

    tag = "🟡 INDICATIVE (forex kapalı/bayat)" if latest["indicative"] else "🟢 GEÇERLİ"
    lines.append(f"**Veri durumu:** {tag}  ·  _{latest['reason']}_")
    lines.append("")

    # ---- Fiyat özeti ----
    lines.append("## Fiyat Özeti")
    lines.append("")
    lines.append("| Metrik | Değer |")
    lines.append("|---|---|")
    lines.append(f"| Ons (XAU/USD) | {_fmt(latest['ons_usd'])} $ |")
    lines.append(f"| USD/TRY | {_fmt(latest['usdtry'], nd=4)} |")
    lines.append(f"| Teorik has gram | {_fmt(latest['theoretical'])} ₺ |")
    lines.append(f"| Piyasa has gram (Kapalıçarşı) | {_fmt(latest['market_has'])} ₺ |")
    lines.append(f"| Perakende gram | {_fmt(latest['gram_retail'])} ₺ |")
    lines.append("")

    # ---- Prim / Makas ----
    lines.append("## Prim & Makas")
    lines.append("")
    lines.append("| Metrik | Değer |")
    lines.append("|---|---|")
    lines.append(f"| **Prim (has, saflık düzeltmeli)** | {_fmt(latest['prim_pct'], '%', 3)} |")
    lines.append(f"| Prim (düzeltmesiz, perakende) | {_fmt(latest['prim_pct_naive'], '%', 3)} |")
    if latest["prim_pct"] is not None and latest["prim_pct_naive"] is not None:
        d = latest["prim_pct_naive"] - latest["prim_pct"]
        lines.append(f"| → Saflık düzeltmesi etkisi | {_fmt(d, ' puan', 3)} |")
    lines.append(f"| Has gram makası | {_fmt(latest['spread_pct'], '%', 3)} |")
    lines.append(f"| Çeyrek primi | {_fmt(latest['quarter_prim_pct'], '%', 2)} |")
    lines.append("")

    band = cfg["stats"]["prim_sane_band_pct"]
    if latest["prim_pct"] is not None:
        if abs(latest["prim_pct"]) <= band:
            lines.append(f"> ✅ Prim ±%{band:g} makul bandında.")
        else:
            lines.append(f"> ⚠️ Prim ±%{band:g} bandının DIŞINDA — veri/şema kontrolü önerilir.")
    lines.append("")

    # ---- Dekompozisyon (son 24s) ----
    lines.append("## Hareket Ayrıştırma (son ~24 saat)")
    lines.append("")
    prev = _prim_at_or_before(con, util.iso(now - timedelta(hours=24)))
    if prev and prev["ts_utc"] != latest["ts_utc"] and prev["ons_usd"] and prev["theoretical"]:
        dec = calc.decompose(
            prev["ons_usd"], prev["usdtry"], prev["prim_pct"] or 0.0,
            latest["ons_usd"], latest["usdtry"], latest["prim_pct"] or 0.0,
        )
        lines.append("| Bileşen | Katkı |")
        lines.append("|---|---|")
        lines.append(f"| Ons (XAU/USD) | {_fmt(dec.ons_pct, '%', 2)} |")
        lines.append(f"| Kur (USD/TRY) | {_fmt(dec.kur_pct, '%', 2)} |")
        lines.append(f"| Kapalıçarşı primi | {_fmt(dec.prim_pct, '%', 2)} |")
        lines.append(f"| **Toplam gram TL** | **{_fmt(dec.total_pct, '%', 2)}** |")
        # E.1: Dolar bazında gram getirisi = toplam − kur = ons + prim
        usd_based = dec.ons_pct + dec.prim_pct
        lines.append(f"| **Dolar bazında gram getirisi** | **{_fmt(usd_based, '%', 2)}** |")
        lines.append("")
        lines.append("> _Dolar bazlı getiri, TL değer kaybından arındırılmış gerçek altın "
                     "getirisidir (\"TL eridiği için mi kazandım?\" sorusunun cevabı)._")
    else:
        lines.append("_Ayrıştırma için yeterli geçmiş yok (≥24s veri gerekir)._")
    lines.append("")

    # ---- Hafta sonu beklentisi vs gerçekleşme (veri yoksa SESSİZ) ----
    try:
        wk = weekend_section(con, cfg)
        if wk:
            lines.extend(wk)
    except Exception as e:
        log.warning("hafta sonu bölümü hata: %s", e)

    # ---- EVDS makro bağlam ----
    try:
        ctx = evds_job.context(cfg)
    except Exception as e:
        log.warning("EVDS bağlam hata: %s", e)
        ctx = {}
    if ctx:
        lines.append("## Makro Bağlam (TCMB EVDS)")
        lines.append("")
        if "politika_faizi" in ctx:
            lines.append(f"- Politika faizi (AOFM): **{_fmt(ctx['politika_faizi'], '%', 2)}**")
        if "mevduat_1yil_net" in ctx:
            lines.append(f"- 1 yıl mevduat: brüt {_fmt(ctx['mevduat_1yil_brut'],'%',2)} → "
                         f"**net {_fmt(ctx['mevduat_1yil_net'],'%',2)}** (stopaj sonrası)")
        if "tufe_yoy" in ctx:
            lines.append(f"- TÜFE (yıllık, {ctx.get('tufe_date','')}): **{_fmt(ctx['tufe_yoy'],'%',2)}**")
        if "enf_bek_12ay" in ctx:
            lines.append(f"- 12 ay TÜFE beklentisi (piyasa): **{_fmt(ctx['enf_bek_12ay'],'%',2)}**")
        if "reel_net_mevduat" in ctx:
            lines.append(f"- **Reel net mevduat faizi: {_fmt(ctx['reel_net_mevduat'],'%',2)}** "
                         f"(altın tutmanın fırsat maliyeti)")
        lines.append("")

    # ---- Kadran / gösterge uzlaşı paneli (E.2) ----
    try:
        panel = indicators.build_panel(cfg, ctx.get("reel_net_mevduat"))
        lines.append("## Gösterge Uzlaşı Paneli")
        lines.append("")
        lines.append("| Gösterge | Değerlendirme | Detay |")
        lines.append("|---|---|---|")
        emoji = {"olumlu": "🟢 olumlu", "nötr": "⚪ nötr",
                 "olumsuz": "🔴 olumsuz", "veri yok": "➖ veri yok"}
        for s in panel["signals"]:
            lines.append(f"| {s.name} | {emoji.get(s.label, s.label)} | {s.detail} |")
        c = panel["consensus"]
        yon = emoji.get(c["yon"], c["yon"])
        lines.append("")
        lines.append(f"**Uzlaşı: {yon}** — skor {c['score']:+d}/{c['n']} gösterge "
                     f"(normalize {c['normalized']:+.2f}). _Altın perspektifinden; "
                     f"kesin yön değil, bağlam._")
        lines.append("")
    except Exception as e:
        log.warning("kadran paneli hata: %s", e)

    # ---- Sinyaller (Bölüm 3) ----
    try:
        from . import signals
        sig = signals.build_signals(cfg)
        lines.append(signals.format_signals_md(sig))
    except Exception as e:
        log.warning("sinyal bölümü hata: %s", e)

    # ---- Grafik yorumu (Bölüm 6) ----
    try:
        from . import chart
        _cm = chart.format_chart_md(chart.build_chart(cfg))
        if _cm:                                   # veri yoksa SESSİZ
            lines.append(_cm)
    except Exception as e:
        log.warning("grafik bölümü hata: %s", e)

    # ---- Veri kalitesi ----
    lines.append("## Veri Kalitesi")
    lines.append("")
    cov = coverage_report(con, cfg, 24)
    _mod = cfg.get("runtime_mode", "actions")
    lines.append(f"- Son 24s veri kapsaması: **%{cov['coverage_pct']:.0f}** "
                 f"({cov['actual']}/{cov['expected']} beklenen kayıt, _{_mod}_ ritmi) · "
                 f"en uzun kesinti: **{cov['max_gap_min']:.0f} dk**")
    # arşiv sağlığı (Actions)
    try:
        h = archive_health(cfg, 24)
        lines.append(f"- Arşiv sağlığı (Actions): **{h['basari']}/{h['beklenen']}** çalışma "
                     f"(%{h['basari_pct']:.0f}) · en uzun boşluk {h['en_uzun_bosluk_dk']:.0f} dk")
        if h["ardisik_basarisiz"] >= 3:
            lines.insert(3, f"> ⚠️ **Arşiv uyarısı:** ~{h['ardisik_basarisiz']} ardışık çalışma "
                            f"başarısız (en uzun boşluk {h['en_uzun_bosluk_dk']:.0f} dk). "
                            f"GitHub Actions kontrol edilmeli.")
    except Exception as e:
        log.warning("arşiv sağlığı hata: %s", e)
    # Uyarı ÖNCELİKLE boşluk tabanlı: Actions'ta günlük çalışma sayısı 10-17 arası oynadığı
    # için sayım oranı tek başına güvenilir bir arıza göstergesi değil.
    _tol = effective_freq_minutes(cfg) * float(
        cfg["alerts"].get("archive_gap_tolerance_factor", 3.0))
    if cov["max_gap_min"] > _tol:
        lines.append(f"  - ⚠️ {cov['max_gap_min']:.0f} dk'lık kesinti (tolerans {_tol:.0f} dk) — "
                     "prim z-skoru yalnız FRESH kayıtları saydığı için tarihçe bozulmaz.")
    n_ticks = con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    n_prim = con.execute("SELECT COUNT(*) FROM prim_history").fetchone()[0]
    n_valid = db.count_valid_prim(con)
    n_ohlc = con.execute("SELECT COUNT(*) FROM ohlc_1m").fetchone()[0]
    zmin = cfg["stats"]["zscore_min_samples"]
    lines.append(f"- Ham tick: **{n_ticks}** · 1dk OHLC bar: **{n_ohlc}**")
    lines.append(f"- Prim kaydı: **{n_prim}** (geçerli: {n_valid})")
    if n_valid < zmin:
        lines.append(f"- Z-skor: ⏳ **yetersiz veri** ({n_valid}/{zmin} geçerli örnek)")
    else:
        series = db.prim_series(con, only_valid=True)
        z = calc.zscore(series[:-1], series[-1], zmin)
        lines.append(f"- Prim z-skoru: **{_fmt(z.value, '', 2)}** (n={z.n})")
    lines.append("")
    lines.append("---")
    lines.append("_Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir._")

    con.close()
    return "\n".join(lines)


def build_weekly_report(cfg: dict) -> str:
    """Pazar akşamı haftalık derin rapor: hafta dekompozisyonu + arşiv/z-skor ilerlemesi."""
    con = db.connect(cfg)
    off = cfg.get("timezone_offset_hours", 3)
    local = util.to_local(util.utcnow(), off)
    from datetime import timedelta
    week_ago = util.iso(util.utcnow() - timedelta(days=7))
    L = [f"# 📅 Haftalık Altın Raporu — {local.strftime('%d.%m.%Y')} (TR)", ""]

    # haftanın dekompozisyonu
    now_row = db.latest_prim(con)
    prev = con.execute("SELECT * FROM prim_history WHERE ts_utc<=? ORDER BY ts_utc DESC LIMIT 1",
                       (week_ago,)).fetchone()
    L.append("## Haftanın Hareketi (dekompozisyon)")
    L.append("")
    if now_row and prev and prev["ons_usd"] and prev["theoretical"]:
        dec = calc.decompose(prev["ons_usd"], prev["usdtry"], prev["prim_pct"] or 0,
                             now_row["ons_usd"], now_row["usdtry"], now_row["prim_pct"] or 0)
        usd_based = dec.ons_pct + dec.prim_pct
        L += [f"- Ons: {dec.ons_pct:+.2f}% · Kur: {dec.kur_pct:+.2f}% · Prim: {dec.prim_pct:+.2f}%",
              f"- **Toplam gram TL: {dec.total_pct:+.2f}%** · Dolar bazlı: {usd_based:+.2f}%"]
    else:
        L.append("_Haftalık dekompozisyon için yeterli geçmiş yok._")
    L.append("")

    # z-skor arşiv ilerlemesi
    zmin = cfg["stats"]["zscore_min_samples"]
    n_valid = db.count_valid_prim(con)
    L += ["## Arşiv İlerlemesi", "",
          f"- Z-skor arşivi: **{n_valid}/{zmin} gün** "
          f"({'hazır ✅' if n_valid >= zmin else 'birikiyor ⏳'})",
          f"- Toplam prim kaydı: {con.execute('SELECT COUNT(*) FROM prim_history').fetchone()[0]}",
          ""]
    con.close()
    # normal günlük içeriği de ekle (kadran, makro, sinyaller)
    L.append("---\n")
    L.append(build_report(cfg))
    return "\n".join(L)


def save_report(cfg: dict, text: str) -> str:
    off = cfg.get("timezone_offset_hours", 3)
    local = util.to_local(util.utcnow(), off)
    fname = f"rapor_{local.strftime('%Y-%m-%d')}.md"
    path = util.abspath(cfg["paths"]["reports_dir"]) / fname
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(util.mask_pii(text), encoding="utf-8")  # commit'e chat_id kaçmasın
    con = db.connect(cfg)
    con.execute("INSERT OR REPLACE INTO reports(date,path,created_utc) VALUES(?,?,?)",
                (local.strftime('%Y-%m-%d'), str(path), util.iso(util.utcnow())))
    con.commit()
    con.close()
    log.info("rapor yazıldı: %s", path)
    return str(path)


def latest_report_path(cfg: dict):
    con = db.connect(cfg)
    row = con.execute("SELECT path FROM reports ORDER BY date DESC LIMIT 1").fetchone()
    con.close()
    return row["path"] if row else None


def main(cfg: dict, send: bool = True) -> str:
    from . import logging_setup
    logging_setup.setup("report", cfg)
    text = build_report(cfg)
    path = save_report(cfg, text)
    if send and cfg["telegram"]["enabled"]:
        try:
            from .telegram_bot import send_message
            send_message(cfg, text)
        except Exception as e:
            log.warning("telegram gönderim hata: %s", e)
    return path


if __name__ == "__main__":
    util.load_env()
    main(util.load_config())
