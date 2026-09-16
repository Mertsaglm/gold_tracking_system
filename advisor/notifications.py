"""Telegram tek kısa karar özeti; fiyat oynadıkça aynı mesajı tekrar göndermez."""
from __future__ import annotations

import os
from pathlib import Path

import requests

from .ledger import digest


def summary(snapshot, url="", max_characters=1000):
    name = "BIST" if snapshot["market"] == "bist" else "ALTIN"
    view = snapshot["strategy"]
    if snapshot.get('health', {}).get('errors'):
        return (f"{name} · SON KOŞU TAMAMLANAMADI\nYeni karar üretilemedi.\n" + '\n'.join(snapshot['health']['errors']) + f"\nSon başarılı kayıt: {snapshot['generated_at'][:16]}\n" + url)[:max_characters]
    ds = snapshot["decisions"]
    trades = [d for d in ds if d.get("execution")]
    actionable = [d for d in ds if d["action"] in {"AL", "SAT"}]
    # Bütün satış/alım satırları önce gelir; gerekçeler yüzünden bir işlem gizlenmez.
    chosen = sorted(actionable, key=lambda d: d['action'] != 'SAT') or sorted(ds, key=lambda d: d["action"] != "TUT")[:2]
    lines = [f"{name} · SANAL PORTFÖY", f"Analiz: {snapshot['analysis_date']}"]
    unit = 'adet' if snapshot['market'] == 'bist' else 'gram'
    for d in chosen:
        ex = d.get("execution")
        lines.append(f"{d['action']} · {d['symbol']}" + (f" · {ex['quantity']} {unit} · {ex['price']:.2f} TL" if ex else ""))
    for d in chosen[:2]:
        if d["reasons"]:
            lines.append(f"• {d['symbol']}: " + d["reasons"][0][:140])
    if not trades and not actionable:
        lines.append(f"Yeni sanal işlem yok. {len(ds)} varlık değerlendirildi.")
    if snapshot.get('news', {}).get('upcoming'):
        e = snapshot['news']['upcoming'][0]
        lines.append(f"Gündem: {e['date']} · {e['title']}")
    equity = view.get("equity_try")
    lines.append((f"Portföy {equity:,.2f} TL · K/Z {view['pnl_try']:+,.2f} TL" if equity is not None else "Portföy değerlemesi eksik.") + f" · nakit {view['cash_try']:,.2f} TL")
    if url:
        lines.append(url)
    return "\n".join(lines)[:max_characters]


def notification_key(snapshot, now):
    return digest({'day': now.date().isoformat(), 'errors': snapshot['health']['errors'],
                   'decisions': [(d['symbol'], d['action'], d['code'], d.get('execution')) for d in snapshot['decisions']]})


def publish_weekly(cfg, snapshot, ledger, now):
    from .calendar import IST
    from .reporting import weekly_text
    local=now.astimezone(IST)
    if not cfg['telegram']['enabled'] or local.weekday()!=4 or local.hour<18 or not snapshot['weekly'].get('ready'):
        return False
    key=f"weekly:{local.isocalendar().year}:{local.isocalendar().week}"
    if key in ledger.keys:return False
    token,chat=os.environ.get('TELEGRAM_BOT_TOKEN'),os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:raise RuntimeError('Telegram bağlantısı eksik.')
    text=weekly_text(snapshot)+'\n'+cfg.get('dashboard_url','')
    try:
        r=requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat,'text':text,'disable_web_page_preview':True},timeout=(5,15))
        if r.status_code!=200 or not r.json().get('ok'):raise RuntimeError('Haftalık özet gönderilemedi.')
    except requests.RequestException:
        raise RuntimeError('Haftalık özet bağlantısı kurulamadı.') from None
    ledger.add('weekly_notification',key,now.isoformat(),text=text)
    ledger.save()
    return True


def publish(root, cfg, snapshot, ledger, now):
    if not cfg["telegram"]["enabled"]:
        return False
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise RuntimeError('Telegram bağlantısı için mevcut bot/chat ayarları eksik.')
    event_key = notification_key(snapshot, now)
    if "telegram:" + event_key in ledger.keys:
        return False
    text = summary(snapshot, cfg.get("dashboard_url", ""), cfg['telegram']['max_characters'])
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=(5, 15))
    except requests.RequestException:
        raise RuntimeError('Telegram bağlantısı kurulamadı.') from None
    # Hata cevabındaki URL/token log'a taşınmaz.
    if r.status_code != 200 or not r.json().get("ok"):
        raise RuntimeError("Telegram özeti gönderilemedi; sonraki koşuda tekrar denenecek.")
    ledger.add("notification", "telegram:" + event_key, now.isoformat(), text=text)
    ledger.save()
    return True
