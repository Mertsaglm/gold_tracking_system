"""Minimal Telegram entegrasyonu (harici bağımlılık yok, sadece requests).

- Raporlar DÜZ METİN gönderilir (Markdown/HTML kaçış tuzağı yok).
- /durum mesajı HTML parse_mode ile (dinamik değerler html.escape ile kaçışlı).
- 4096 karakter sınırı için bölme.
- run_bot: long-polling ile /durum, /rapor; ilk /start chat_id'si loglanır+doğrulanır.
"""
from __future__ import annotations

import html
import logging
import re
import time

import requests

from . import db, util

log = logging.getLogger("telegram")

API = "https://api.telegram.org/bot{token}/{method}"
TG_LIMIT = 4096


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


def allowed_chats(cfg: dict) -> set[str]:
    """İzinli sohbet kimlikleri: .env TELEGRAM_CHAT_ID + config ekstralar."""
    ids = set()
    owner = util.env("TELEGRAM_CHAT_ID")
    if owner:
        ids.add(str(owner))
    for x in cfg.get("telegram", {}).get("extra_allowed_chat_ids", []) or []:
        ids.add(str(x))
    return ids


def is_allowed(chat_id: str, allowed: set[str]) -> bool:
    return str(chat_id) in allowed


def _chunks(text: str, size: int = TG_LIMIT - 200):
    """Satır sınırlarını koruyarak böl (tablo/paragraf ortadan kesilmesin)."""
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > size:
            if cur:
                out.append(cur)
            # tek satır bile sığmıyorsa sert böl
            while len(line) > size:
                out.append(line[:size])
                line = line[size:]
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        out.append(cur)
    return out


def _md_to_plain(text: str) -> str:
    """Markdown süslerini temizleyip Telegram için okunur düz metne çevirir."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # **kalın**
    text = re.sub(r"`(.+?)`", r"\1", text)          # `kod`
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)   # başlık #
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)     # alıntı >
    return text


def send_message(cfg: dict, text: str, chat_id: str | None = None,
                 parse_mode: str | None = None) -> int:
    """Düz metin (varsayılan) veya HTML gönderir. Gönderilen parça sayısını döner."""
    cid = chat_id or _chat_id()
    payload = _md_to_plain(text) if parse_mode is None else text
    n = 0
    for part in _chunks(payload):
        data = {"chat_id": cid, "text": part, "disable_web_page_preview": "true"}
        if parse_mode:
            data["parse_mode"] = parse_mode
        _call("sendMessage", **data)
        n += 1
    # chat_id loglanmaz (gizlilik); son 3 hane yeter
    log.info("telegram: %d parça gönderildi (chat=…%s, mode=%s)", n, str(cid)[-3:], parse_mode or "plain")
    return n


# ---------- Komutlar ----------
def _cmd_durum(cfg: dict) -> str:
    con = db.connect(cfg)
    latest = db.latest_prim(con)
    off = cfg.get("timezone_offset_hours", 3)
    if latest is None:
        con.close()
        return "Henüz veri yok."
    tag = "🟡 indicative" if latest["indicative"] else "🟢 geçerli"
    local = util.to_local(util.utcnow(), off).strftime("%H:%M")
    e = html.escape
    def g(k, f="%.2f"):
        v = latest[k]
        return e(f % v) if v is not None else "—"
    con.close()
    return (
        f"<b>Anlık Durum</b> ({local} TR) {tag}\n"
        f"Ons: <code>{g('ons_usd')}$</code>  ·  USD/TRY: <code>{g('usdtry','%.4f')}</code>\n"
        f"Teorik has gram: <code>{g('theoretical')}₺</code>\n"
        f"Piyasa has gram: <code>{g('market_has')}₺</code>\n"
        f"<b>Prim: {g('prim_pct','%.3f')}%</b>  ·  Makas: {g('spread_pct','%.3f')}%\n"
        f"Çeyrek primi: {g('quarter_prim_pct','%.2f')}%\n"
        f"<i>{e(latest['reason'] or '')}</i>"
    )


def _cmd_net(cfg: dict, text: str) -> str:
    from . import calculators as clc
    parts = text.split()
    try:
        amount = float(parts[1]) if len(parts) > 1 else 100000.0
        months = int(parts[2]) if len(parts) > 2 else 12
        gold = float(parts[3]) if len(parts) > 3 else None
    except ValueError:
        return "Kullanım: /net <tutar> <ay> [altın%]  (ör. /net 100000 12 30)"
    res = clc.compare_instruments(cfg, amount, months, gold)
    be = clc.break_even_month(cfg, amount, gold)
    out = clc.format_compare(res)
    out += f"\nBanka↔fon kırılım: {be} ay" if be else "\nKırılım yok."
    return out


def _cmd_bilezik(cfg: dict, text: str) -> str:
    from . import calculators as clc
    parts = text.split()
    try:
        brut = float(parts[1]) if len(parts) > 1 else 20.0
        isc = float(parts[2]) if len(parts) > 2 else 20.0
        price = float(parts[3]) if len(parts) > 3 else (clc._latest_has_price(cfg) or 6200.0)
    except ValueError:
        return "Kullanım: /bilezik <gram> <işçilik%> [gramfiyat]  (ör. /bilezik 20 20)"
    return clc.format_bilezik(clc.bilezik_basabas(cfg, brut, isc, price))


def _cmd_rapor(cfg: dict) -> str:
    con = db.connect(cfg)
    row = con.execute("SELECT path FROM reports ORDER BY date DESC LIMIT 1").fetchone()
    con.close()
    if row and util.abspath(row["path"]).exists():
        return util.abspath(row["path"]).read_text(encoding="utf-8")
    from .report import build_report
    return build_report(cfg)


def run_bot(cfg: dict) -> None:
    global log
    from . import logging_setup
    log = logging_setup.setup("telegram_bot", cfg)
    offset = None
    timeout = cfg["telegram"]["poll_timeout"]
    allowed = allowed_chats(cfg)
    log.info("Telegram bot başladı (long-polling). İzinli sohbet sayısı=%d", len(allowed))
    while True:
        try:
            resp = _call("getUpdates", timeout=timeout, offset=offset if offset else "")
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("channel_post")
                if not msg:
                    continue
                text = (msg.get("text") or "").strip().lower()
                cid = str(msg["chat"]["id"])
                # Yetkilendirme: izinli olmayan sohbet sessizce yoksayılır
                if not is_allowed(cid, allowed):
                    log.warning("yetkisiz sohbet komut denedi: …%s (yoksayıldı)", cid[-3:])
                    continue
                if text.startswith("/start"):
                    send_message(cfg, "Merhaba! Komutlar:\n/durum — anlık fiyat + prim\n"
                                      "/rapor — son gün sonu raporu", chat_id=cid)
                elif text.startswith("/durum"):
                    send_message(cfg, _cmd_durum(cfg), chat_id=cid, parse_mode="HTML")
                elif text.startswith("/rapor"):
                    send_message(cfg, _cmd_rapor(cfg), chat_id=cid)
                elif text.startswith("/net"):
                    send_message(cfg, _cmd_net(cfg, text), chat_id=cid)
                elif text.startswith("/bilezik"):
                    send_message(cfg, _cmd_bilezik(cfg, text), chat_id=cid)
                elif text.startswith("/aipaket"):
                    from . import aipaket
                    send_message(cfg, aipaket.build_prompt(cfg), chat_id=cid)
                elif text.startswith("/grafik"):
                    from . import chart
                    # refresh=False: uzun yoklama döngüsü 30 sn'lik yfinance çağrısında
                    # asılmasın; günlük OHLC'yi daily_job zaten güncelliyor.
                    _t = chart.format_chart_md(chart.build_chart(cfg, refresh=False))
                    send_message(cfg, _t or "Grafik verisi yok.", chat_id=cid)
                elif text.startswith("/yardim") or text.startswith("/help"):
                    send_message(cfg, "Komutlar:\n/durum · /rapor\n"
                                      "/net <tutar> <ay> [altın%] — enstrüman karşılaştırma\n"
                                      "/bilezik <gram> <işçilik%> [gramfiyat] — başabaş\n"
                                      "/aipaket — AI'a yapıştırılacak veri paketi\n"
                                      "/grafik — destek/direnç + gösterge teyidi",
                                 chat_id=cid)
        except Exception as e:
            log.warning("bot döngü hata: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    util.load_env()
    run_bot(util.load_config())
