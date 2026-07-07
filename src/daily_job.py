"""Bölüm 2 — Otonom günlük rapor orkestratörü (Actions).

import_actions → EVDS günlük → (pazartesi mutabakat) → rapor (pazar: haftalık) → Telegram.
Actions'ta günde bir çalışır; DB + rapor commit'lenir (workflow tarafından).
"""
from __future__ import annotations

import logging

from . import util

log = logging.getLogger("daily_job")


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
        log.warning("import hata: %s", e)
        result["import_hata"] = str(e)

    # 2) EVDS günlük güncelleme
    try:
        from .evds_job import daily_update
        result["evds"] = daily_update(cfg)
    except Exception as e:
        log.warning("evds hata: %s", e)

    # 3) Pazartesi mutabakat
    if weekday == 0:
        try:
            from .reconcile import reconcile
            result["mutabakat"] = reconcile(cfg)
        except Exception as e:
            log.warning("mutabakat hata: %s", e)

    # 4) Rapor (pazar → haftalık derin) + Telegram
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
        log.warning("rapor hata: %s", e)
        result["rapor_hata"] = str(e)

    log.info("daily_job: %s", {k: v for k, v in result.items() if k != "import"})
    return result


if __name__ == "__main__":
    util.load_env()
    print(run(util.load_config()))
