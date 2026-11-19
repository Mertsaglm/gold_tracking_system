"""Telegram tek kısa karar özeti; fiyat oynadıkça aynı mesajı tekrar göndermez."""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from time import sleep

import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError

from .calendar import IST
from .ledger import digest

TRADE_REASONS = {
    'stop': 'zarar sınırı', 'target': 'kâr hedefi', 'time_exit': 'izleme süresi doldu',
    'forecast_reversal': 'tahmin tersine döndü', 'sma50_exit': 'trend bozuldu',
    'sma50_entry': 'trend alımı', 'cost_adjusted_opportunity': 'masraf sonrası fırsat',
}


def summary(snapshot, url="", max_characters=1000):
    name = "BIST" if snapshot["market"] == "bist" else "ALTIN"
    view = snapshot["strategy"]
    if snapshot.get('health', {}).get('errors'):
        return (f"{name} · SON KOŞUDA VERİ SORUNU\nYeni işlem için veri doğrulanamadı.\n" + '\n'.join(snapshot['health']['errors']) + f"\nKayıt zamanı: {snapshot['generated_at'][:16]} UTC\n" + url)[:max_characters]
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
    issues = snapshot.get('health', {}).get('analysis_issues', {})
    if issues:
        lines.append('Analiz güncelliği uyarısı: ' + ', '.join(issues))
    equity = view.get("equity_try")
    lines.append((f"Portföy {equity:,.2f} TL · K/Z {view['pnl_try']:+,.2f} TL" if equity is not None else "Portföy değerlemesi eksik.") + f" · nakit {view['cash_try']:,.2f} TL")
    if url:
        lines.append(url)
    return "\n".join(lines)[:max_characters]


def closing_day(snapshot, now):
    monitoring = snapshot.get('monitoring', {})
    health = snapshot['health']
    if monitoring.get('phase') != 'valuation':
        return None
    day = now.astimezone(IST).date().isoformat()
    if snapshot['market'] == 'gold':
        return day
    expected = health.get('expected_analysis_date')
    if expected == day or (expected and monitoring.get('closing_refresh')):
        return expected
    return None


def _closing_complete(snapshot):
    health = snapshot['health']
    expected = health.get('expected_quotes', 0)
    return (expected > 0 and health.get('quote_coverage') == expected
            and snapshot['analysis_date'] == health.get('expected_analysis_date')
            and not health.get('errors') and not health.get('analysis_issues')
            and snapshot['strategy'].get('valuation_complete') is not False)


def _closing_summary(snapshot, ledger, day, url, limit):
    market = 'BIST' if snapshot['market'] == 'bist' else 'ALTIN'
    health = snapshot['health']
    counts = Counter(d['action'] for d in snapshot['decisions'])
    session_checks = []
    fills = []
    for event in ledger.events:
        if event['kind'] not in ('session_check', 'fill'):
            continue
        if datetime.fromisoformat(event['at']).astimezone(IST).date().isoformat() != day:
            continue
        data = event['data']
        if event['kind'] == 'session_check' and data.get('in_execution_window'):
            session_checks.append(data)
        elif event['kind'] == 'fill' and data.get('book') in ('strategy', 'benchmark'):
            fills.append(data)
    complete = sum(c['expected_quotes'] > 0 and c['valid_quotes'] == c['expected_quotes']
                   and c.get('decisions', 0) >= c['expected_quotes'] and not c.get('errors')
                   and not c.get('analysis_issues') and not c.get('data_blocked_symbols')
                   for c in session_checks)
    lines = [f'{market} · GÜN SONU · {day}',
             f"Tam fiyat+karar: {complete}/{len(session_checks)} çalışan işlem çevrimi.",
             f"Son geçerli fiyat: {health.get('quote_coverage', 0)}/{health.get('expected_quotes', 0)}"
             f" · analiz: {snapshot['analysis_date']}",
             'Son kararlar: ' + (', '.join(f'{k} {v}' for k, v in sorted(counts.items())) or 'yok')]
    if not _closing_complete(snapshot):
        lines.append('Uyarı: kapanış verisi veya çevrimde eksik var.')
    for book, label in (('strategy', 'Strateji'), ('benchmark', 'Pasif')):
        booked = [f for f in fills if f['book'] == book]
        buys = sum(f['side'] == 'BUY' for f in booked)
        lines.append(f'{label} gerçekleşen: {buys} AL, {len(booked) - buys} SAT.')
        if book == 'strategy' and booked:
            for fill in booked[:5]:
                side = 'AL' if fill['side'] == 'BUY' else 'SAT'
                reason = TRADE_REASONS.get(fill.get('reason'))
                price = f" · {fill['price']:.2f} TL" if fill.get('price') is not None else ''
                lines.append(f"{side} {fill['symbol']}{price}" + (f' · {reason}' if reason else ''))
            if len(booked) > 5:
                lines.append(f'{len(booked) - 5} işlem daha panelde.')
    if not any(f['book'] == 'strategy' for f in fills) and snapshot['decisions']:
        reasons = Counter(d['reasons'][0] for d in snapshot['decisions'] if d.get('reasons'))
        if reasons:
            lines.append('Örnek gerekçe: ' + reasons.most_common(1)[0][0][:140])
    equity = snapshot['strategy'].get('equity_try')
    if equity is not None:
        lines.append(f'Strateji değeri: {equity:,.2f} TL')
    body = '\n'.join(lines)
    if url and len(url) + 1 < limit:
        return body[:limit - len(url) - 1] + '\n' + url
    return body[:limit]


def notification_key(snapshot, now):
    state = {'day': now.astimezone(IST).date().isoformat(), 'errors': snapshot['health']['errors'],
             'decisions': [(d['symbol'], d['action'], d['code'], d.get('execution')) for d in snapshot['decisions']]}
    # Kararlar aynı kalırken yeni veri uyarısı da teslim edilmelidir.
    if snapshot['health'].get('analysis_issues'):
        state['analysis_issues'] = snapshot['health']['analysis_issues']
    if snapshot['strategy'].get('valuation_complete') is False:
        state['valuation_complete'] = False
    return digest(state)


def delivered(ledger, snapshot, *, require_closing=True):
    """Son GÖNDERİLEN durumla karşılaştır; A→hata→A iyileşmesi kaybolmasın."""
    at = datetime.fromisoformat(snapshot['generated_at'])
    report_day = closing_day(snapshot, at)
    if report_day and require_closing:
        previous = next((e['data'] for e in reversed(ledger.events)
                         if e['kind'] == 'notification' and e['data'].get('report_day') == report_day), None)
        # Bir eksik kapanış bildirildiyse sonradan toparlanan kapanışı da ilet.
        return previous is not None and (previous.get('closing_complete') or not _closing_complete(snapshot))
    key = notification_key(snapshot, at)
    last = next((e for e in reversed(ledger.events) if e['kind'] == 'notification'), None)
    if last is None:
        return False
    return last['data'].get('state_key', last['key'].removeprefix('telegram:')) == key


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
    at = datetime.fromisoformat(snapshot['generated_at'])
    if at.tzinfo is None or not -60 <= (now-at).total_seconds() <= cfg['max_quote_age_minutes'] * 60:
        raise ValueError('Bildirim için görünüm eski veya zamanı geçersiz; güncel cycle gerekli.')
    event_key = notification_key(snapshot, at)
    if delivered(ledger, snapshot):
        return False
    report_day = closing_day(snapshot, at)
    url, limit = cfg.get('dashboard_url', ''), cfg['telegram']['max_characters']
    text = (_closing_summary(snapshot, ledger, report_day, url, limit) if report_day
            else summary(snapshot, url, limit))
    for attempt in range(3):
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=(5, 15))
            break
        except requests.RequestException as error:
            underlying = error.args[0] if error.args else None
            before_send = (isinstance(error, requests.ConnectTimeout)
                           or isinstance(underlying, MaxRetryError)
                           and isinstance(underlying.reason, ConnectTimeoutError))
            if not before_send or attempt == 2:
                raise RuntimeError(f'Telegram teslimi doğrulanamadı ({type(error).__name__}).') from None
            sleep(2 ** attempt)
    # Hata cevabındaki URL/token log'a taşınmaz.
    try:
        response = r.json()
    except ValueError:
        raise RuntimeError(f'Telegram teslimi doğrulanamadı (HTTP {r.status_code}).') from None
    if r.status_code != 200 or not response.get("ok"):
        raise RuntimeError("Telegram özeti gönderilemedi; sonraki koşuda tekrar denenecek.")
    # Aynı durumun sonraki geri dönüşü ayrı makbuzdur; anlık fiyat değişimi spam üretmez.
    receipt = digest({'state': event_key, 'snapshot_at': snapshot['generated_at'],
                      'previous_receipt': next((e['key'] for e in reversed(ledger.events) if e['kind']=='notification'), None)})
    result = response.get('result', {})
    report_data = {'report_day': report_day, 'closing_complete': _closing_complete(snapshot)} if report_day else {}
    ledger.add("notification", "telegram:" + receipt, now.isoformat(), text=text, **report_data,
               state_key=event_key, snapshot_at=snapshot['generated_at'],
               snapshot_ledger_hash=snapshot.get('health', {}).get('ledger_hash'),
               message_id=result.get('message_id'), telegram_date=result.get('date'))
    ledger.save()
    return True
