"""Minimal Telegram entegrasyonu (harici bağımlılık yok, sadece requests).

- send_message: rapor/mesaj gönderir.
- run_bot: long-polling ile /rapor ve /durum komutlarını dinler.
"""
from __future__ import annotations

import html
import logging
import time
from datetime import timedelta

import requests

from . import calc, db, util

log = logging.getLogger("telegram")

API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    t = util.env("TELEGRAM_BOT_TOKEN")
    if not t:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tanımlı değil (.env)")
    return t


def _chat_id() -> str:
    c = util.env("TELEGRAM_CHAT_ID")
    if not c:
        raise RuntimeError("TELEGRAM_CHAT_ID tanımlı değil (.env)")
    return c


def _call(method: str, **params):
    url = API.format(token=_token(), method=method)
    r = requests.post(url, data=params, timeout=35)
    r.raise_for_status()
    return r.json()


def _chunks(text: str, size: int = 3800):
    for i in range(0, len(text), size):
        yield text[i:i + size]


def send_message(cfg: dict, text: str, chat_id: str | None = None) -> None:
    cid = chat_id or _chat_id()
    for part in _chunks(text):
        _call("sendMessage", chat_id=cid, text=part,
              parse_mode="Markdown", disable_web_page_preview="true")
    log.info("telegram mesaj gönderildi (chat=%s)", cid)


# ---------- Komutlar ----------
def _cmd_durum(cfg: dict) -> str:
    con = db.connect(cfg)
    latest = db.latest_prim(con)
    off = cfg.get("timezone_offset_hours", 3)
    if latest is None:
        con.close()
        return "Henüz veri yok."
    legs_reason = latest["reason"]
    tag = "🟡 indicative" if latest["indicative"] else "🟢 geçerli"
    local = util.to_local(util.utcnow(), off).strftime("%H:%M")
    con.close()
    return (
        f"*Anlık Durum* ({local} TR) {tag}\n"
        f"Ons: `{latest['ons_usd']:.2f}$`  ·  USD/TRY: `{latest['usdtry']:.4f}`\n"
        f"Teorik has gram: `{latest['theoretical']:.2f}₺`\n"
        f"Piyasa has gram: `{latest['market_has']:.2f}₺`\n"
        f"*Prim: {latest['prim_pct']:.3f}%*  ·  Makas: "
        f"{('%.3f%%' % latest['spread_pct']) if latest['spread_pct'] is not None else '—'}\n"
        f"Çeyrek primi: "
        f"{('%.2f%%' % latest['quarter_prim_pct']) if latest['quarter_prim_pct'] is not None else '—'}\n"
        f"_{legs_reason}_"
    )


def _cmd_rapor(cfg: dict) -> str:
    path = db_latest_report(cfg)
    if path and util.abspath(path).exists():
        return util.abspath(path).read_text(encoding="utf-8")
    # yoksa anlık üret
    from .report import build_report
    return build_report(cfg)


def db_latest_report(cfg: dict):
    con = db.connect(cfg)
    row = con.execute("SELECT path FROM reports ORDER BY date DESC LIMIT 1").fetchone()
    con.close()
    return row["path"] if row else None


def run_bot(cfg: dict) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    offset = None
    timeout = cfg["telegram"]["poll_timeout"]
    log.info("Telegram bot başladı (long-polling).")
    while True:
        try:
            resp = _call("getUpdates", timeout=timeout,
                         offset=offset if offset else "")
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("channel_post")
                if not msg:
                    continue
                text = (msg.get("text") or "").strip().lower()
                cid = str(msg["chat"]["id"])
                if text.startswith("/durum"):
                    send_message(cfg, _cmd_durum(cfg), chat_id=cid)
                elif text.startswith("/rapor"):
                    send_message(cfg, _cmd_rapor(cfg), chat_id=cid)
                elif text.startswith("/start") or text.startswith("/yardim") or text.startswith("/help"):
                    send_message(cfg, "Komutlar:\n/durum — anlık fiyat + prim\n/rapor — son gün sonu raporu", chat_id=cid)
        except Exception as e:
            log.warning("bot döngü hata: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    util.load_env()
    run_bot(util.load_config())
