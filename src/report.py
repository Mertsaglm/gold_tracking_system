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
    'collector' modunda (7/24 canlı toplayıcı) truncgil poll_seconds geçerlidir.
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


def reel_faiz_tabani_satiri(ctx: dict) -> list[str]:
    """Reel net mevduatın HANGİ enflasyon serisiyle hesaplandığını + duyarlılığını yazar.

    NEDEN VAR (denetim 2026-08-11): bu tek sayı çekirdek kolun tek kapı
    değişkeni ve rapor dayanağını hiç söylemiyordu. `ozellikler.py` bilinçli
    olarak **12 ay beklentiyi** kullanıyor (TÜFE serisi bayat; sessiz yedeğe
    düşme replay'de kesişim kuralını ihlal ederdi) — doğru bir seçim, ama
    SONUCU tamamen bu seçime bağlı: ölçüldü, beklentiyle %12.85 (kural
    tetikler), gerçekleşen TÜFE ile %6.87 (tetiklemez). Okuyan bunu görmeden
    sayıya güvenemez.
    """
    bek, brut = ctx.get("enf_bek_12ay"), ctx.get("mevduat_1yil_brut")
    net = ctx.get("mevduat_1yil_net")
    if bek is None or net is None:
        return []
    out = [f"  - _Taban: **12 ay enflasyon BEKLENTİSİ** ({bek:.2f}%) — "
           f"gerçekleşen TÜFE değil._"]
    tufe = ctx.get("tufe_yoy")
    if tufe is not None:
        alt = ((1 + net / 100) / (1 + tufe / 100) - 1) * 100
        tar = ctx.get("tufe_date", "")
        out.append(f"  - _Duyarlılık: gerçekleşen TÜFE ({tufe:.2f}%, {tar}) "
                   f"kullanılsaydı **{alt:+.2f}%** olurdu._")
    return out


def bildirim_saglik_metni(saglik: dict) -> str:
    """Bildirim hattı arıza defterini rapor satırına çevirir (saf, testli).

    Boş string = hat sağlıklı, rapor sessiz kalır. Dolu string = Mert'in
    GÖRMESİ gereken bir kesinti var; ekranın en üstüne konur.
    """
    n = int((saglik or {}).get("ardisik_hata", 0) or 0)
    if n <= 0:
        return ""
    son = (saglik.get("son_hata") or "bilinmiyor").replace("\n", " ")
    ne_zaman = (saglik.get("son_hata_utc") or "")[:16].replace("T", " ")
    return (f"> 🔴 **BİLDİRİM HATTI ARIZALI:** {n} ardışık gönderim hatası. "
            f"Anomali uyarıları Telegram'a **GİTMİYOR**. "
            f"Son hata ({ne_zaman} UTC): `{son}`")


def bildirim_hatti_satiri(cfg: dict) -> str:
    """Arıza defterini diskten okur; okunamazsa SESSİZ kalır (rapor bloklanmaz)."""
    try:
        st = util.read_json(cfg["alerts"]["state_file"], {}) or {}
        return bildirim_saglik_metni(st.get("saglik", {}))
    except Exception as e:                            # noqa: BLE001
        log.warning("bildirim sağlık defteri okunamadı: %s", e)
        return ""


def gunluk_adim_satiri(cfg: dict) -> str:
    """Dün patlayan KRİTİK OLMAYAN adımlar (denetim 2026-08-28, B-19).

    `daily_job` yalnız import+rapor'u kritik sayar; kalan 6 adım patlarsa
    Actions yeşil kalır. Sessiz kalan bir arıza yaşayan bir arızadır — bildirim
    hattı satırıyla (ADR #011) AYNI yerde görünür olsun.

    Boş string = tüm adımlar geçti.
    """
    try:
        st = util.read_json(cfg["alerts"]["state_file"], {}) or {}
        blok = (st.get("saglik") or {}).get("gunluk_adimlar") or {}
        hatalar = blok.get("hatalar") or {}
    except Exception as e:                            # noqa: BLE001
        log.warning("günlük adım defteri okunamadı: %s", e)
        return ""
    if not hatalar:
        return ""
    adlar = ", ".join(sorted(hatalar))
    ilk = str(next(iter(hatalar.values())))[:160].replace("\n", " ")
    return (f"> ⚠️ **GÜNLÜK İŞ EKSİK ÇALIŞTI:** şu adımlar patladı — **{adlar}**. "
            f"Actions yeşil göründü çünkü bunlar kritik adım değil. "
            f"İlk hata: `{ilk}`")


def prim_turetilmis_satiri(con) -> str:
    """Prim'in iki bacağı bağımsız değilse ekranın en üstüne kırmızı satır.

    NEDEN RAPORDA (denetim 2026-08-28, B-03/B-21): ADR #013 ons'u gram ile aynı
    satıcıya taşıyınca prim bir KİMLİĞE çöktü (`gram_has ≡ ons × kur × 0.995`,
    ons sadeleşiyor). 8 gün boyunca 855 test yeşil kaldı, rapor her gün
    "✅ Prim ±%3 makul bandında" bastı ve kapı sayacı ilerlemeye devam etti.
    Sessiz kalan tek şey ölçümün kendisiydi. Bildirim hattı satırının (ADR #011)
    kanıtlanmış kalıbı burada da geçerli: arıza görünür olmazsa yaşar.

    Boş string = son gün bağımsız ölçüm taşıyor, rapor sessiz kalır.
    """
    row = con.execute(
        "SELECT substr(ts_utc,1,10) g, COUNT(*) n FROM prim_history "
        "WHERE reason = 'turetilmis' GROUP BY g ORDER BY g DESC LIMIT 1"
    ).fetchone()
    if not row:
        return ""
    son_gun = con.execute(
        "SELECT substr(MAX(ts_utc),1,10) FROM prim_history").fetchone()[0]
    if row[0] != son_gun:
        return ""                                   # arıza geçmişte kalmış
    toplam = con.execute(
        "SELECT COUNT(DISTINCT substr(ts_utc,1,10)) FROM prim_history "
        "WHERE reason = 'turetilmis'").fetchone()[0]
    return (f"> 🔴 **PRİM ÖLÇÜM TAŞIMIYOR:** piyasa bacağı teorik bacaktan "
            f"TÜRETİLMİŞ — ons prim formülünde sadeleşiyor, geriye satıcının "
            f"kendi saflık çarpanı kalıyor. {toplam} gün kapı sayacının "
            f"**dışında**. Prim, prim z-skoru ve hafta sonu beklentisi bugün "
            f"karar taşımıyor.")


def classify_gap(prim_gap_min: float, collection_gap_min, tol_min: float):
    """Boşluğun ARIZA mı yoksa KAYNAK KALİTESİ mi olduğunu ayırır (saf, testli).

    İki farklı şey aynı kelimeyle ("kesinti") raporlanınca yanlış alarm doğuyordu:
    - prim boşluğu  : prim_history'deki boşluk — kaynak boş dönerse de büyür
    - çekim boşluğu : Actions gerçekten çalışmadıysa büyür (arşiv CSV'si)
    Örn. 2026-07-22'de prim boşluğu 545 dk raporlandı ama Actions tam zamanında
    çalışmıştı (çekim boşluğu 217 dk); fark, truncgil'in boş dönmesiydi.

    Döner: (seviye, mesaj) — seviye "ok" | "kaynak" | "ariza".
    """
    if prim_gap_min <= tol_min:
        return ("ok", None)
    # Actions çekimi sağlıklıysa sorun altyapıda değil, kaynak verisinde
    if collection_gap_min is not None and collection_gap_min <= tol_min:
        return ("kaynak",
                f"{prim_gap_min:.0f} dk prim boşluğu (tolerans {tol_min:.0f} dk) — "
                f"Actions düzenli çalıştı (çekim boşluğu {collection_gap_min:.0f} dk); "
                "boşluk kaynağın boş dönmesinden. Prim z-skoru yalnız FRESH "
                "kayıtları saydığı için tarihçe bozulmaz.")
    return ("ariza",
            f"{prim_gap_min:.0f} dk'lık çekim kesintisi (tolerans {tol_min:.0f} dk) — "
            "GitHub Actions kontrol edilmeli. Prim z-skoru yalnız FRESH kayıtları "
            "saydığı için tarihçe bozulmaz.")


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

    # ---- HÜKÜM (raporun EN BAŞI) ----
    # Neden burada: sinyaller eskiden 8. bölümdeydi ve kimse oraya kadar
    # okumuyordu. Kullanıcının rapordan beklediği tek şey "bugün ne yapayım?" —
    # o cevap ilk ekranda olmalı, Telegram'da da öyle görünür.
    if cfg.get("karar", {}).get("enabled", False):
        try:
            from . import karar
            lines.append(karar.format_karar_md(karar.build_karar(cfg)))
        except Exception as e:
            log.warning("hukum blogu hata: %s", e)

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
            lines += reel_faiz_tabani_satiri(ctx)
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
                 f"en uzun **prim** boşluğu: **{cov['max_gap_min']:.0f} dk**")
    # arşiv sağlığı (Actions) — çekim boşluğu, prim boşluğundan AYRI ölçülür
    _cekim_gap = None
    try:
        h = archive_health(cfg, 24)
        _cekim_gap = h["en_uzun_bosluk_dk"]
        lines.append(f"- Arşiv sağlığı (Actions): **{h['basari']}/{h['beklenen']}** çalışma "
                     f"(%{h['basari_pct']:.0f}) · en uzun **çekim** boşluğu {_cekim_gap:.0f} dk")
        if h["ardisik_basarisiz"] >= 3:
            lines.insert(3, f"> ⚠️ **Arşiv uyarısı:** ~{h['ardisik_basarisiz']} ardışık çalışma "
                            f"başarısız (en uzun çekim boşluğu {_cekim_gap:.0f} dk). "
                            f"GitHub Actions kontrol edilmeli.")
    except Exception as e:
        log.warning("arşiv sağlığı hata: %s", e)
    # Bildirim hattı sağlığı — `notify.saglik_guncelle` defterinden okunur.
    # NEDEN RAPORDA: 2026-07-29'da hat kırıldı ve 13 gün boyunca HİÇBİR yer
    # "gönderemedim" demedi (Actions adımı continue-on-error ile yeşildi).
    # Sessiz arıza sınıfını kapatan şey düzeltme değil, bu satır.
    _bh = bildirim_hatti_satiri(cfg)
    if _bh:
        lines.insert(3, _bh)
    # Günlük işin sessizce yuttuğu adım hataları (denetim 2026-08-28, B-19)
    _ga = gunluk_adim_satiri(cfg)
    if _ga:
        lines.insert(3, _ga)
    # Bağımsızlık nöbetçisi — prim ölçüm mü, kimlik mi? (denetim 2026-08-28)
    try:
        _tr = prim_turetilmis_satiri(con)
        if _tr:
            lines.insert(3, _tr)
    except Exception as e:                            # noqa: BLE001
        log.warning("türetilmiş prim satırı okunamadı: %s", e)
    # Uyarı ÖNCELİKLE boşluk tabanlı: Actions'ta günlük çalışma sayısı 10-17 arası oynadığı
    # için sayım oranı tek başına güvenilir bir arıza göstergesi değil.
    _tol = effective_freq_minutes(cfg) * float(
        cfg["alerts"].get("archive_gap_tolerance_factor", 3.0))
    _seviye, _mesaj = classify_gap(cov["max_gap_min"], _cekim_gap, _tol)
    if _mesaj:
        _ikon = "ℹ️" if _seviye == "kaynak" else "⚠️"
        lines.append(f"  - {_ikon} {_mesaj}")
    n_ticks = con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    n_prim = con.execute("SELECT COUNT(*) FROM prim_history").fetchone()[0]
    n_valid = db.count_valid_prim(con)
    n_ohlc = con.execute("SELECT COUNT(*) FROM ohlc_1m").fetchone()[0]
    zmin = cfg["stats"]["zscore_min_samples"]
    lines.append(f"- Ham tick: **{n_ticks}** · 1dk OHLC bar: **{n_ohlc}**")
    n_days = db.count_valid_prim_days(con)
    lines.append(f"- Prim kaydı: **{n_prim}** (geçerli: {n_valid} · {n_days} gün)")
    if n_days < zmin:
        lines.append(f"- Z-skor: ⏳ **arşiv birikiyor** ({n_days}/{zmin} gün)")
    else:
        series = db.prim_series(con)
        z = calc.zscore(series[:-1], series[-1], zmin)
        lines.append(f"- Prim z-skoru: **{_fmt(z.value, '', 2)}** (n={z.n})")
        # Çeyrek z'si de gösterilir: kapı açılınca "çeyrek |z| > 2" bildirimi
        # ateşlenebiliyor; tetikleyen sayının raporda görünmemesi tutarsızlık olurdu.
        qser = db.prim_series(con, column="quarter_prim_pct")
        if len(qser) >= 2:
            qz = calc.zscore(qser[:-1], qser[-1], zmin)
            if qz.value is not None:
                lines.append(f"- Çeyrek primi z-skoru: **{_fmt(qz.value, '', 2)}** "
                             f"(n={qz.n}) · _sezon düzeltmesi yok_")
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
    n_days = db.count_valid_prim_days(con)
    L += ["## Arşiv İlerlemesi", "",
          f"- Z-skor arşivi: **{n_days}/{zmin} gün** "
          f"({'hazır ✅' if n_days >= zmin else 'birikiyor ⏳'})",
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
