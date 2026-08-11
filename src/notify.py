"""Bölüm 1 — Bildirim motoru (Actions 15 dk workflow'una entegre).

Rehber 6.2 eşik tablosu + bildirim yorgunluğu (24s soğuma + günlük tavan) + piyasa
durum makinesi saygısı (üç bacak FRESH değilse anomali bildirimi bastırılır).

Saf çekirdek (evaluate_thresholds, apply_cooldown) birim testlidir. Durum Actions
stateless olduğundan repoda data/alert_state.json'da tutulur ve workflow commit'ler.
"""
from __future__ import annotations

import html
import json
import logging
import math
import statistics
from datetime import datetime, timedelta, timezone

from . import calc, db, util

log = logging.getLogger("notify")

# Telegram HTML modunda metin içinde SERBEST bırakılabilecek tek şey desteklenen
# etiketlerdir; `<`, `>`, `&` kaçırılmazsa API 400 döner ve mesaj HİÇ gitmez.
# Bunu şablonun kendisinde çözüyoruz: dinamik alanlar daima kaçırılır, böylece
# gelecekte eklenen bir eşik metni "<" içerse bile hat kırılmaz.
TG_HTML_ETIKETLERI = ("b", "i", "u", "s", "code", "pre", "a", "tg-spoiler",
                      "blockquote", "em", "strong", "ins", "strike", "del")


# ---------- SAF ÇEKİRDEK (testli) ----------
def evaluate_thresholds(ctx: dict, cfg: dict) -> list[dict]:
    """Eşikleri değerlendirir. ctx alanları None ise o kural pas geçilir.

    all_fresh False (hafta sonu/tatil) → anomali kuralları BASTIRILIR (indicative).
    """
    a = cfg["alerts"]
    out = []
    all_fresh = ctx.get("all_fresh", True)

    def add(tip, kural, deger, gerekce, gecersizlik):
        out.append({"tip": tip, "kural": kural, "deger": deger,
                    "gerekce": gerekce, "gecersizlik": gecersizlik})

    # Anomali kuralları yalnız üç bacak FRESH iken
    if all_fresh:
        prim = ctx.get("prim")
        primz = ctx.get("prim_z")
        if prim is not None and abs(prim) > a["prim_abs_pct"]:
            add("prim_sapma", f"|prim| > %{a['prim_abs_pct']}", prim,
                f"Prim %{prim:+.2f} teorik değerden saptı.",
                "Prim bandına dönerse (|%|<1.5) geçersiz.")
        if primz is not None and abs(primz) > a["prim_z"]:
            add("prim_z", f"|z| > {a['prim_z']}", primz,
                f"Prim z-skoru {primz:+.2f} (tarihsel aşırılık).",
                "z ortalamaya dönerse (|z|<1) geçersiz.")
        # MAKAS: yüzdelik TEK BAŞINA eşik olamaz — pN, tanımı gereği kayıtların
        # %(100−N)'ini aşar. Makas serisi dar ve durağan (ölçüldü 2026-08-11,
        # N=313 FRESH kayıt: medyan %0.0146, p90 %0.0158 = medyanın 1.08 katı,
        # gözlenen en yüksek %0.0260 = 1.78 katı). Yani "p90 aşıldı" cümlesi
        # piyasa hakkında hiçbir şey söylemiyordu; alarm her gün ateşleniyordu
        # (teslim edilen 19 bildirimin 12'si buydu) ve günlük tavanı (6) yiyordu.
        # Bu, L-010'un aynısı: girdiden bağımsız aynı çıktıyı üreten bir "ölçüm"
        # ölçüm değil KİMLİKTİR.
        # Çözüm: yüzdelik KALIR ama yanına MADDİ bir taban eklenir — makasın
        # gerçekten açılması (medyanın katı) şart. 2.0× eşiğinde 313 kaydın
        # HİÇBİRİ ateşlemezdi; doğrusu da bu, çünkü bu dönemde makas patlaması
        # olmadı. Gerçek bir stresde (kaynak makası açar) alarm yine çalışır.
        sp, p90 = ctx.get("spread"), ctx.get("spread_p90")
        med = ctx.get("spread_medyan")
        k = a.get("spread_min_medyan_carpani", 2.0)
        taban = k * med if med else None
        if sp is not None and p90 is not None and sp > p90 and (
                taban is None or sp > taban):
            add("makas", f"makas > p{a['spread_percentile']} ve {k:g}× medyan", sp,
                f"Makas %{sp:.3f} — tarihsel p{a['spread_percentile']} (%{p90:.3f}) "
                f"VE medyanın {k:g} katı (%{taban:.3f}) üstünde: makas açıldı."
                if taban else
                f"Makas %{sp:.3f} tarihsel p{a['spread_percentile']} (%{p90:.3f}) üstünde.",
                "Makas normale dönerse geçersiz.")
        move, atr = ctx.get("daily_move"), ctx.get("atr")
        if move is not None and atr and move > a["daily_move_atr"] * atr:
            add("gunluk_hareket", f"hareket > {a['daily_move_atr']}×ATR", move,
                f"Günlük hareket {move:.0f}₺ > {a['daily_move_atr']}×ATR({atr:.0f}).",
                "Volatilite normalleşirse geçersiz.")
        qz = ctx.get("quarter_z")
        if qz is not None and abs(qz) > a["quarter_z"]:
            add("ceyrek_prim", f"çeyrek |z| > {a['quarter_z']}", qz,
                f"Çeyrek primi z {qz:+.2f} — fiziki alımda gram/çeyrek tercihi değişebilir.",
                "Çeyrek primi normale dönerse geçersiz.")
    return out


def apply_cooldown(alerts: list[dict], state: dict, now_iso: str,
                   cooldown_hours: float, daily_cap: int) -> tuple[list[dict], dict]:
    """Soğuma (aynı tip 24s) + günlük tavan. (gonderilecek, yeni_state) döner."""
    now = datetime.fromisoformat(now_iso)
    last = dict(state.get("last_sent", {}))
    today = now.date().isoformat()
    daily = dict(state.get("daily", {}))
    count = daily.get(today, 0)
    to_send = []
    for al in alerts:
        if count >= daily_cap:
            break
        prev = last.get(al["tip"])
        if prev:
            age_h = (now - datetime.fromisoformat(prev)).total_seconds() / 3600
            if age_h < cooldown_hours:
                continue                      # soğumada
        to_send.append(al)
        last[al["tip"]] = now_iso
        count += 1
    daily = {today: count}                    # sadece bugünü tut
    # State'in DİĞER anahtarları korunur (`saglik` gibi). Eskiden burada sıfırdan
    # bir sözlük kuruluyordu ve arıza defteri, gönderilecek bildirim olmayan HER
    # sessiz koşumda siliniyordu: hat kırıkken rapordaki uyarı bir sonraki
    # koşumda kendiliğinden kaybolurdu — yani görünürlük katmanı, korumaya
    # çalıştığı şeyin aynısına kurban gidiyordu. Üretimde yakalandı (2026-08-11).
    out = dict(state)
    out["last_sent"] = last
    out["daily"] = daily
    return to_send, out


def damgayi_geri_al(onceki: dict, yeni: dict, basarisiz_tipler: list[str],
                    gun: str) -> dict:
    """Gönderilemeyen bildirimlerin `last_sent` damgasını ve tavan sayacını GERİ ALIR.

    `apply_cooldown` damgayı gönderimden ÖNCE atıyor (saf kalabilmesi için).
    Damga geri alınmazsa gönderilemeyen bir bildirim 24 saat boyunca
    "gönderilmiş" sayılır, soğumaya takılır ve bir daha DENENMEZ — sessiz
    kesintiyi kalıcı hâle getiren ikinci mekanizma budur.
    """
    if not basarisiz_tipler:
        return yeni
    last = dict(yeni.get("last_sent", {}))
    onceki_last = onceki.get("last_sent", {})
    for tip in basarisiz_tipler:
        if tip in onceki_last:
            last[tip] = onceki_last[tip]      # eski damgaya dön
        else:
            last.pop(tip, None)               # hiç gönderilmemişti: damgayı sil
    daily = dict(yeni.get("daily", {}))
    daily[gun] = max(0, daily.get(gun, 0) - len(basarisiz_tipler))
    out = dict(yeni)
    out["last_sent"] = last
    out["daily"] = daily
    return out


def saglik_guncelle(state: dict, now_iso: str, denenen: int,
                    hatalar: list[dict]) -> dict:
    """Bildirim hattının sağlık defteri — `data/alert_state.json` içinde yaşar.

    NEDEN VAR: 2026-07-29'daki kesinti 13 gün sürdü çünkü hiçbir yer "gönderemedim"
    demiyordu; Actions adımı `continue-on-error: true` ile yeşil kalıyordu. Sayaç
    burada tutulur, günlük rapor buradan okuyup Mert'e söyler. Arızayı önlemek
    yeterli değil — GÖRÜNÜR olması gerekiyor.
    """
    s = dict(state.get("saglik", {}))
    if hatalar:
        s["ardisik_hata"] = int(s.get("ardisik_hata", 0)) + len(hatalar)
        s["son_hata_utc"] = now_iso
        s["son_hata"] = f"{hatalar[0]['tip']}: {hatalar[0]['hata']}"[:300]
    elif denenen:
        s["ardisik_hata"] = 0
        s["son_basari_utc"] = now_iso
        s.pop("son_hata", None)
        s.pop("son_hata_utc", None)
    out = dict(state)
    out["saglik"] = s
    return out


# ---------- IO / bağlam ----------
def _load_state(cfg) -> dict:
    return util.read_json(cfg["alerts"]["state_file"], {"last_sent": {}, "daily": {}})


def _save_state(cfg, state) -> None:
    util.write_json(cfg["alerts"]["state_file"], state)


def _atr_from_history(con, window=14, bugun=None):
    """ATR(14) — kapanış-kapanış yaklaşımı, history_daily'den.

    history_daily'yi daily_job her gün tazeler (`history.update_recent`). Tazelenmezse
    ATR sabit kalır ve "günlük hareket" alarmı yanlış eşikle çalışır — bir dönem
    böyle oldu, bkz. ai/DECISIONS.md #004.

    BUGÜN DIŞLANIR: `update_recent` hafta içi her koşumda o günün YARIM barını da
    yazıyor (yfinance ∩ EVDS ikisi de aynı-gün satırı döndürüyor). Yarım bar
    ATR'yi hem bozar hem de gün içinde her çalıştırmada değiştirir — eşik
    kayan bir hedefe dönerdi.
    """
    bugun = bugun or util.local_today()
    rows = con.execute(
        "SELECT gram_teorik FROM history_daily WHERE date < ? "
        "ORDER BY date DESC LIMIT ?", (bugun, window + 1)
    ).fetchall()
    prices = [r["gram_teorik"] for r in reversed(rows)]
    if len(prices) < window + 1:
        return None
    trs = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    return sum(trs) / len(trs)


def _latest_csv_row(cfg):
    """En yeni arşiv CSV satırını okur (Actions'ta taze veri DB'den değil buradadır)."""
    import csv
    import glob
    files = sorted(glob.glob(str(util.abspath("data/archive") / "*.csv")))
    if not files:
        return None
    rows = list(csv.DictReader(open(files[-1], encoding="utf-8")))
    return rows[-1] if rows else None


def _ctx_from_csv(cfg, con, row) -> dict:
    """Taze CSV satırından güncel prim/makas/çeyrek; tarihsel bağlam DB'den."""
    from .market_calendar import MarketCalendar
    inst = cfg["instruments"]
    def f(k):
        v = row.get(k)
        try:
            return float(v) if v not in (None, "", "None") else None
        except ValueError:
            return None
    ons, usd, gram_has = f("ons_usd"), f("usdtry"), f("gram_has_sell")
    if not (ons and usd and gram_has):
        return None
    theo = calc.theoretical_gram(ons, usd, inst["troy_ounce_gram"])
    prim = calc.prim_pct(gram_has, theo)
    gh_b = f("gram_has_buy")
    spread = calc.spread_pct(gh_b, gram_has) if gh_b else None
    ceyrek = f("ceyrek_sell")
    quarter = None
    if ceyrek and gram_has:
        c = inst["coins"]["ceyrek"]
        quarter = calc.quarter_prim_pct(ceyrek, gram_has, c["gross_g"], c["milyem"])
    ts = datetime.fromisoformat(row["ts_utc"]).astimezone(timezone.utc)
    cal = MarketCalendar(cfg)
    all_fresh = not (cal.is_weekend_closed_forex(ts) or cal.is_us_gold_holiday(ts))
    return {"ons": ons, "usd": usd, "gram_has": gram_has, "theoretical": theo,
            "prim": prim, "spread": spread, "quarter": quarter,
            "all_fresh": all_fresh, "ts": ts}


def build_context(cfg: dict) -> dict:
    """Güncel değerler taze CSV'den (varsa), tarihsel bağlam commit'li DB'den."""
    con = db.connect(cfg)
    csv_row = _latest_csv_row(cfg)
    fresh = _ctx_from_csv(cfg, con, csv_row) if csv_row else None
    latest = db.latest_prim(con)
    if fresh is None and latest is None:
        con.close()
        return {"all_fresh": False}
    # güncel değerler: taze CSV öncelikli, yoksa DB
    cur_prim = fresh["prim"] if fresh else latest["prim_pct"]
    cur_spread = fresh["spread"] if fresh else latest["spread_pct"]
    cur_theo = fresh["theoretical"] if fresh else latest["theoretical"]
    all_fresh = fresh["all_fresh"] if fresh else (not bool(latest["indicative"]))
    zmin = cfg["stats"]["zscore_min_samples"]
    n_days = db.count_valid_prim_days(con)
    prim_z = None
    if n_days >= zmin and cur_prim is not None:
        series = db.prim_series(con)
        z = calc.zscore(series, cur_prim, zmin)     # güncel primin arşive karşı z'si
        prim_z = z.value
    # Makas tabanı: yalnız FRESH kayıtlar. Eskiden filtre YOKTU ve hafta sonu/
    # indicative satırlar da yüzdeliği besliyordu — oysa z-skor kapısı yalnız
    # FRESH sayıyor. İki metrik aynı arşivden farklı tabanlar çıkarıyordu.
    spreads = [r[0] for r in con.execute(
        "SELECT spread_pct FROM prim_history WHERE spread_pct IS NOT NULL"
        " AND indicative = 0 AND weekend = 0").fetchall()]
    p = cfg["alerts"]["spread_percentile"]
    spread_p90 = spread_medyan = None
    if len(spreads) >= 20:
        spreads.sort()
        idx = int(p / 100 * (len(spreads) - 1))
        spread_p90 = spreads[idx]
        spread_medyan = statistics.median(spreads)
    # Günlük hareket: güncel teorik vs SON KAPANMIŞ günün kapanışı.
    # `date < bugun` şart: `update_recent` hafta içi bugünün yarım barını da
    # yazıyor. Filtresiz "en son satır", günlük rapor koştuktan sonra BUGÜNÜN
    # kendi yarım kapanışına dönüyordu — yani alarm fiyatı kendisiyle
    # karşılaştırıp farkı ~0 buluyor ve akşam saatlerinde hiç ateşlenemiyordu.
    bugun_local = util.local_today()
    atr = _atr_from_history(con, bugun=bugun_local)
    yrow = con.execute("SELECT gram_teorik FROM history_daily WHERE date < ? "
                       "ORDER BY date DESC LIMIT 1", (bugun_local,)).fetchone()
    daily_move = abs(cur_theo - yrow["gram_teorik"]) if (yrow and cur_theo) else None
    # Çeyrek primi z'si — prim z ile AYNI kapıya tabi (tutarlılık).
    # Kapı açılana dek None; bu artık "unutulmuş" değil, gerekçesi yazılı bir bekleme.
    # SEZON DÜZELTMESİ YOK: ziynet talebinde (düğün sezonu vb.) yıllık örüntü olabilir
    # ama düzeltme için yıllar süren arşiv gerekir. Düz z, sezonu "anomali" sanabilir —
    # bu sınır rapora da yazılır, sessizce güçlü sinyal gibi sunulmaz.
    cur_quarter = fresh.get("quarter") if fresh else (
        latest["quarter_prim_pct"] if latest is not None else None)
    quarter_z = None
    if n_days >= zmin and cur_quarter is not None:
        qseries = db.prim_series(con, column="quarter_prim_pct")
        if qseries:
            quarter_z = calc.zscore(qseries, cur_quarter, zmin).value
    con.close()
    return {
        "all_fresh": all_fresh,
        "prim": cur_prim, "prim_z": prim_z,
        "spread": cur_spread, "spread_p90": spread_p90,
        "spread_medyan": spread_medyan,
        "daily_move": daily_move, "atr": atr,
        "quarter": cur_quarter, "quarter_z": quarter_z,
    }


def tg_kacir(s) -> str:
    """Telegram HTML metin kaçışı: `&`, `<`, `>`. Tırnaklara DOKUNMAZ.

    quote=False bilinçli: Telegram yalnız bu üç karakteri şart koşuyor; tırnağı
    da kaçırmak metni `&#x27;` çöplüğüne çevirirdi.
    """
    return html.escape(str(s), quote=False)


def _format_alert(al: dict) -> str:
    """Bildirim metni. Dinamik alanların HEPSİ kaçırılır — bu bir stil tercihi
    değil, hattın çalışma şartıdır.

    2026-07-29 → 08-10 arası 13 gün boyunca HİÇBİR anomali bildirimi gitmedi:
    `prim_sapma`'nın geçersizlik metnindeki `(|%|<1.5)` ifadesini Telegram etiket
    başlangıcı sanıp 400 döndürdü. `prim_sapma` sırada birinci olduğu için
    arkasındaki `makas`/`gunluk_hareket` de hiç denenmedi. Bkz. ai/LESSONS.md L-018.
    """
    e = tg_kacir
    return (f"🔔 <b>{e(al['kural'])}</b>\n"
            f"{e(al['gerekce'])}\n"
            f"<i>Geçersizlik: {e(al['gecersizlik'])}</i>\n"
            f"— Genel bilgilendirme, yatırım tavsiyesi değildir.")


def _gonder(cfg, to_send: list[dict], send_message) -> tuple[int, list[dict]]:
    """Her bildirimi BAĞIMSIZ gönderir; biri patlarsa diğerleri yine gider.

    Eski hâlde döngü tek `raise` ile kırılıyordu: sıradaki `prim_sapma` 400 alınca
    `makas` ve `gunluk_hareket` hiç denenmiyor, `_save_state` hiç çalışmıyordu.
    """
    ok, hatalar = 0, []
    for al in to_send:
        try:
            send_message(cfg, _format_alert(al), parse_mode="HTML")
            ok += 1
        except Exception as e:                       # noqa: BLE001 — hat kırılmasın
            hatalar.append({"tip": al["tip"], "hata": f"{type(e).__name__}: {e}"})
            log.error("BİLDİRİM GÖNDERİLEMEDİ (%s): %s", al["tip"], e)
    return ok, hatalar


def run(cfg: dict, test_mode: bool = False) -> dict:
    from . import logging_setup
    logging_setup.setup("notify", cfg)
    from .telegram_bot import send_message
    now_iso = util.utcnow().isoformat()
    bugun_utc = now_iso[:10]

    if test_mode:
        msg = ("🧪 <b>Test bildirimi</b>\nBildirim motoru canlı ve Telegram'a "
               "ulaşabiliyor. Gerçek eşiklerden bağımsız tek seferlik test.\n"
               "<i>Geçersizlik: yok (test).</i>")
        send_message(cfg, msg, parse_mode="HTML")
        return {"test": True, "gonderildi": 1}

    ctx = build_context(cfg)
    state = _load_state(cfg)
    a = cfg["alerts"]

    # Hafta sonu/tatil: anomali bastırılır; yalnız "pazartesi beklentisi" (günde 1)
    if not ctx.get("all_fresh", True):
        weekend_alert = []
        if ctx.get("prim") is not None:
            weekend_alert = [{
                "tip": "weekend_expectation",
                "kural": "Hafta sonu — pazartesi beklentisi",
                "deger": ctx["prim"],
                "gerekce": (f"Forex kapalı; Kapalıçarşı gramı donmuş teoriğe göre "
                            f"%{ctx['prim']:+.2f} sapmada — piyasanın pazartesi için "
                            f"fiyatladığı hareket."),
                "gecersizlik": "Pazartesi açılışta ons/kur güncellenince yeniden hesaplanır.",
            }]
        to_send, new_state = apply_cooldown(weekend_alert, state, now_iso,
                                            a["cooldown_hours"], 1)
        ok, hatalar = _gonder(cfg, to_send, send_message)
        new_state = damgayi_geri_al(state, new_state,
                                    [h["tip"] for h in hatalar], bugun_utc)
        new_state = saglik_guncelle(new_state, now_iso, len(to_send), hatalar)
        _save_state(cfg, new_state)              # DAİMA: arıza defteri de yazılmalı
        log.info("hafta sonu: %d beklenti mesajı (%d hata)", ok, len(hatalar))
        return {"weekend": True, "gonderildi": ok, "hatalar": hatalar}

    alerts = evaluate_thresholds(ctx, cfg)
    to_send, new_state = apply_cooldown(alerts, state, now_iso,
                                        a["cooldown_hours"], a["daily_cap"])
    ok, hatalar = _gonder(cfg, to_send, send_message)
    new_state = damgayi_geri_al(state, new_state,
                                [h["tip"] for h in hatalar], bugun_utc)
    new_state = saglik_guncelle(new_state, now_iso, len(to_send), hatalar)
    _save_state(cfg, new_state)                  # DAİMA: arıza defteri de yazılmalı
    log.info("bildirim: %d tetik, %d gönderildi, %d HATA (soğuma/tavan sonrası)",
             len(alerts), ok, len(hatalar))
    return {"tetik": len(alerts), "gonderildi": ok, "hatalar": hatalar,
            "tipler": [x["tip"] for x in to_send if
                       x["tip"] not in {h["tip"] for h in hatalar}]}


if __name__ == "__main__":
    import sys
    util.load_env()
    cfg = util.load_config()
    print(run(cfg, test_mode=("test" in sys.argv)))
