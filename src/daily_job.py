"""Bölüm 2 — Otonom günlük rapor orkestratörü (Actions).

import_actions → EVDS günlük → OHLC → history_daily → (pazartesi mutabakat)
→ rapor (pazar: haftalık) → Telegram.
Actions'ta günde bir çalışır; DB + rapor commit'lenir (workflow tarafından).

history_daily adımı ATR ve "günlük hareket" alarmlarının kaynağını tazeler; buraya
bağlı olmadığı için bir dönem donuk kalmıştı (bkz. ai/DECISIONS.md #004).
"""
from __future__ import annotations

import logging

from . import util

log = logging.getLogger("daily_job")

# Bu adımlar patlarsa iş BAŞARISIZ sayılır ve süreç 1 ile çıkar → Actions kırmızı.
# Diğerleri (evds/ohlc/history/prova/tahmin/grafik) bir gün atlanabilir; rapor
# yine de anlamlıdır ve ertesi gün kendini onarırlar.
#
# NEDEN VAR: eskiden altı adımın hepsi `except → log.warning` ile yutuluyordu ve
# `run()` hiçbir koşulda yükselmiyordu. `logs/` gitignore'da olduğu için uyarılar
# commit'lenmiyor; yani `import_actions` veya rapor günlerce patlasa Actions
# YEŞİL kalıyor, tek işaret "Telegram'a mesaj düşmedi" oluyordu. Bu, ADR #004'te
# 17 gün fark edilmeyen `history_daily` donmasının aynı zeminidir.
KRITIK_ADIMLAR = ("import", "rapor")


def _hata(result: dict, adim: str, e: Exception) -> None:
    """Adım hatasını TEK yere yazar: log + `result["hatalar"]`.

    Tek yol olması şart — eskiden bazı adımlar yalnız log'luyor, bazıları
    `result`'a da yazıyordu; hangi adımın patladığı çıktıdan okunamıyordu.
    """
    log.warning("%s hata: %s", adim, e)
    result.setdefault("hatalar", {})[adim] = str(e)


def basarisiz_mi(result: dict) -> list[str]:
    """Kritik adımlardan patlayanların listesi (boşsa iş başarılı)."""
    return [a for a in KRITIK_ADIMLAR if a in result.get("hatalar", {})]


def _zskor_prova(cfg: dict) -> dict:
    """Kuru prova ölçümünü JSONL'a ekler (append-only, günde 1 satır).

    Bildirim göndermez; yalnız "kapı açık olsaydı z ne olurdu" kaydını tutar.
    """
    import json

    from . import db, signals
    st = cfg.get("stats", {})
    if not st.get("zskor_prova_aktif"):
        return {"aktif": False}
    con = db.connect(cfg)
    try:
        olcum = signals.zscore_dry_run(cfg, con)
    finally:
        con.close()
    olcum["ts_utc"] = util.utcnow().isoformat()
    path = util.abspath(st.get("zskor_prova_dosyasi", "data/zskor_prova.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(olcum, ensure_ascii=False) + "\n")
    return {k: olcum[k] for k in ("gun", "z_kayit_tabani", "z_gun_tabani",
                                  "tetiklenir_kayit", "tetiklenir_gun")}


def run(cfg: dict) -> dict:
    from . import logging_setup
    logging_setup.setup("daily_job", cfg)
    off = cfg.get("timezone_offset_hours", 3)
    local = util.to_local(util.utcnow(), off)
    weekday = local.weekday()          # Mon=0 ... Sun=6
    result = {"tarih": local.date().isoformat(), "gun": weekday}

    # 1) Actions CSV arşivini DB'ye işle
    try:
        from .import_actions import import_all
        result["import"] = import_all(cfg)
    except Exception as e:
        _hata(result, "import", e)

    # 2) EVDS günlük güncelleme
    try:
        from .evds_job import daily_update
        result["evds"] = daily_update(cfg)
    except Exception as e:
        _hata(result, "evds", e)

    # 3) Günlük OHLC (grafik yorumu için) — artımlı, son N günü yeniden yazar
    try:
        from .ohlc_hist import update_ohlc_daily
        result["ohlc"] = update_ohlc_daily(cfg)
    except Exception as e:
        _hata(result, "ohlc", e)

    # 3b) history_daily (ATR + günlük hareket alarmlarının kaynağı) — artımlı
    try:
        from .history import update_recent
        result["history"] = update_recent(cfg)
    except Exception as e:
        _hata(result, "history", e)

    # 3c) Z-skor kuru provası — kapı açılmadan dağılımı kaydet (bildirim YOK)
    try:
        result["zskor_prova"] = _zskor_prova(cfg)
    except Exception as e:
        _hata(result, "zskor_prova", e)

    # 3d) Tahmin kaydı — hüküm ver, girişi doldur, vadesi geleni çöz.
    # SIRA ÖNEMLİ: rapordan (adım 5) ÖNCE olmalı ki rapordaki karne bugünün
    # çözümlerini içersin. Çözüm kaydettikten sonra gelir — aynı koşuda
    # yazılan tahmin zaten vadesi dolmadığı için çözülmez, zararsız.
    # Bu adım `data/altin.sql` dump'ına yazar (dbdump._TABLES) — Actions
    # stateless olduğu için kayıt ancak böyle hayatta kalır.
    try:
        from . import db as _db, tahmin
        _con = _db.connect(cfg)
        try:
            result["tahmin_kaydedilen"] = len(tahmin.kaydet(cfg, _con))
            result["tahmin_giris"] = tahmin.girisleri_doldur(cfg, _con)
            result["tahmin_cozulen"] = tahmin.cozumle(cfg, _con)
        finally:
            _con.close()
    except Exception as e:
        _hata(result, "tahmin", e)

    # 4) Pazartesi mutabakat
    if weekday == 0:
        try:
            from .reconcile import reconcile
            result["mutabakat"] = reconcile(cfg)
        except Exception as e:
            _hata(result, "mutabakat", e)

    # 5) Rapor (pazar → haftalık derin) + Telegram
    from .report import build_report, build_weekly_report, save_report
    try:
        text = build_weekly_report(cfg) if weekday == 6 else build_report(cfg)
        path = save_report(cfg, text)
        result["rapor"] = path
        if cfg["telegram"]["enabled"]:
            from .telegram_bot import send_message
            send_message(cfg, text)
            result["telegram"] = "gonderildi"
    except Exception as e:
        _hata(result, "rapor", e)

    # 6) Görsel grafik — rapordan SONRA ve AYRI try/except'te.
    # Ayrı olmasının sebebi: matplotlib ağır bir bağımlılık ve grafik metnin
    # EKİDİR, yerine geçmez. Çizim ya da gönderim patlarsa raporun gitmiş
    # olması değişmez; iş bu adımda bitmiş sayılır.
    if cfg.get("chart", {}).get("gorsel", {}).get("gunluk_gonder", True):
        try:
            from . import grafik_ciz
            p = grafik_ciz.ciz(cfg)
            result["grafik"] = p
            if p and cfg["telegram"]["enabled"]:
                from .telegram_bot import send_photo
                send_photo(cfg, p, caption="Altın Takip — günlük grafik")
        except Exception as e:
            _hata(result, "grafik", e)

    # ADIM HATALARINI GÖRÜNÜR YERE YAZ (denetim 2026-08-28, B-19).
    # `KRITIK_ADIMLAR` yalnız import+rapor; diğer 6 adım (evds, ohlc, history,
    # zskor_prova, tahmin, mutabakat, grafik) patlarsa Actions YEŞİL kalıyor,
    # hata yalnız `result["hatalar"]` sözlüğüne yazılıp stdout'a basılıyor ve
    # `logs/` gitignore'da. Yani `history` günlerce donsa Mert'in göreceği tek
    # işaret raporun içindeki dolaylı bir sayı olurdu — ADR #004'teki 17 gün
    # fark edilmeyen donmanın aynı zemini.
    #
    # Yeni altyapı kurulmuyor: bildirim hattı için kurulan ve İŞE YARADIĞI
    # kanıtlanmış defter (ADR #011, `alert_state.json → saglik`) genişletiliyor.
    try:
        yol = cfg["alerts"]["state_file"]
        st = util.read_json(yol, {}) or {}
        sag = dict(st.get("saglik", {}))
        sag["gunluk_adimlar"] = {
            "utc": util.utcnow().isoformat(),
            "hatalar": dict(result.get("hatalar", {})),
        }
        st["saglik"] = sag
        util.write_json(yol, st)
    except Exception as e:                            # noqa: BLE001 — rapor bloklanmasın
        # Defterin kendisi de bir adımdır: sessizce log'a düşmesi, kapatmaya
        # çalıştığımız sessiz-arıza sınıfının ta kendisi olurdu (ADR #008 K-6).
        _hata(result, "saglik_defteri", e)

    log.info("daily_job: %s", {k: v for k, v in result.items() if k != "import"})
    return result


if __name__ == "__main__":
    import sys

    util.load_env()
    _res = run(util.load_config())
    print(_res)
    _kritik = basarisiz_mi(_res)
    if _kritik:
        # Actions bu adımı kırmızıya düşürsün: sonraki adımlar (dbdump + commit)
        # atlanır, yani yarım/eski veri commit'lenmez ve arıza GÖRÜNÜR olur.
        print(f"KRITIK ADIM BASARISIZ: {', '.join(_kritik)}", file=sys.stderr)
        sys.exit(1)
