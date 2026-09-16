"""V2 işlem penceresi ve vade aynı tarihli takvimi kullanır."""
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

IST = ZoneInfo('Europe/Istanbul')


def load(root):
    path = Path(root) / 'holidays_tr.yaml'
    if not path.exists():
        return {'full_days': [], 'half_days': [], 'years': [], 'available': False}
    raw = yaml.safe_load(path.read_text()) or {}
    full = raw.get('tam_gun', raw.get('tr', {}))
    half = raw.get('yarim_gun', {})
    return {'full_days': sorted({str(d) for days in full.values() for d in days}),
            'half_days': sorted({str(d) for days in half.values() for d in days}),
            'years': sorted(map(str, full)), 'available': True}


def trading_day(day, cfg):
    day = date.fromisoformat(day) if isinstance(day, str) else day
    closed = cfg.get('calendar', {}).get('full_days', cfg.get('holidays', []))
    return day.weekday() < 5 and day.isoformat() not in closed


def add_sessions(day, count, cfg):
    day = date.fromisoformat(day) if isinstance(day, str) else day
    if count < 0:
        raise ValueError('Vade negatif olamaz.')
    while count:
        day += timedelta(days=1)
        if trading_day(day, cfg):
            count -= 1
    return day.isoformat()


def window(day, cfg):
    times = cfg.get('execution_window', {})
    opening, closing = times.get('open', '10:15'), times.get('close', '17:45')
    if day.isoformat() in cfg.get('calendar', {}).get('half_days', []):
        closing = times.get('half_day_close', '12:15')
    return (datetime.fromisoformat(day.isoformat() + 'T' + t).replace(tzinfo=IST)
            for t in (opening, closing))


def session_block(now, cfg):
    local = now.astimezone(IST)
    cal = cfg.get('calendar', {})
    if cal and (not cal.get('available') or str(local.year) not in cal.get('years', [])):
        return 'İşlem yılı için doğrulanmış takvim kaydı yok.'
    if not trading_day(local.date(), cfg):
        return 'Piyasa tatilinde yeni sanal işlem yapılmaz.'
    start, end = window(local.date(), cfg)
    if not start <= local <= end:
        return 'İşlem penceresi dışında; uygun saat bekleniyor.'
    return None
