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


def require_coverage(start, end, cfg):
    """Eksik yıl yüzünden nakitte kalan bir sınav geçerli performans değildir."""
    cal = cfg.get('calendar')
    if cal is None:  # Takvimsiz sentetik araştırma/test çağrıları.
        return
    years = {str(y) for y in range(date.fromisoformat(start).year, date.fromisoformat(end).year + 1)}
    missing = years - set(cal.get('years', []))
    if not cal.get('available') or missing:
        raise ValueError('Sınav takvimi eksik; doğrulanmış yıl gerekli: ' + ', '.join(sorted(missing or years)))


def add_sessions(day, count, cfg):
    day = date.fromisoformat(day) if isinstance(day, str) else day
    if count < 0:
        raise ValueError('Vade negatif olamaz.')
    while count:
        day += timedelta(days=1)
        if trading_day(day, cfg):
            count -= 1
    return day.isoformat()


def window(day, cfg, purpose='execution'):
    times = cfg.get(purpose + '_window', cfg.get('execution_window', {}))
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


def phase(now, cfg):
    """İşlem saatini uzatmak, kapanış ihalesinde dolum uydurmamalı."""
    local = now.astimezone(IST)
    cal = cfg.get('calendar', {})
    if cal and (not cal.get('available') or str(local.year) not in cal.get('years', [])):
        return 'closed'
    if not trading_day(local.date(), cfg):
        return 'closed'
    start, end = window(local.date(), cfg, 'observation')
    if not start <= local <= end:
        return 'closed'
    start, end = window(local.date(), cfg)
    if start <= local < end:
        entry_start, entry_end = window(local.date(), cfg, 'entry')
        return 'entry' if entry_start <= local < entry_end else 'protection'
    return 'valuation'


def monitoring_snapshot(now, cfg):
    """Panel ve nöbetçinin kullanacağı aynı takvim sözleşmesi."""
    local = now.astimezone(IST)
    return {'phase': phase(now, cfg), 'timezone': 'Europe/Istanbul',
            'execution_window': cfg.get('execution_window', {}),
            'entry_window': cfg.get('entry_window', cfg.get('execution_window', {})),
            'observation_window': cfg.get('observation_window', cfg.get('execution_window', {})),
            'calendar': cfg.get('calendar', {'available':False,'years':[],'full_days':[],'half_days':[]}), 'checked_on': local.date().isoformat(),
            'note': 'Gözlem saati ile yeni işlem saati ayrıdır; referans fiyat anlık emir defteri değildir.'}


def last_closed_session(now, cfg):
    """Gece yarısı duvar tarihini değiştirir, tamamlanan seansı değiştirmez."""
    local = now.astimezone(IST)
    day = local.date()
    close = '12:40' if day.isoformat() in cfg.get('calendar', {}).get('half_days', []) else '18:10'
    if not trading_day(day, cfg) or local.strftime('%H:%M') < close:
        day -= timedelta(days=1)
        while not trading_day(day, cfg):
            day -= timedelta(days=1)
    cal = cfg.get('calendar')
    if cal is not None and (not cal.get('available') or str(day.year) not in cal.get('years', [])):
        raise ValueError('Kapanış seansı için doğrulanmış takvim kaydı yok.')
    return day
