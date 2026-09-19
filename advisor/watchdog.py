"""Ayrı workflow'dan salt-okur gözlem: kendi baktığı süreci kilitlemez."""
from datetime import datetime, timedelta
import json
from pathlib import Path

from .calendar import IST, load, trading_day, window
from .ledger import Ledger
from .marketdata import price_problem


def expected_slot(now, cfg):
    cutoff = now.astimezone(IST) - timedelta(minutes=cfg.get('watchdog_grace_minutes', 90))
    for offset in range(370):
        day = cutoff.date() - timedelta(days=offset)
        if not trading_day(day, cfg):
            continue
        start, end = window(day, cfg)
        slot = start.replace(minute=17, second=0, microsecond=0)
        slots = []
        while slot <= end:
            if slot <= cutoff:
                slots.append(slot)
            slot += timedelta(hours=1)
        if slots:
            return slots[-1]
    raise ValueError('Beklenen işlem aralığı bulunamadı.')


def inspect(root, now):
    from .service import configuration
    root = Path(root)
    cfg = configuration(root)
    cfg['calendar'] = load(root)
    due = expected_slot(now, cfg)
    findings = []
    def flag(code, message):
        findings.append({'code': code, 'message': message})
    try:
        state = root / 'data/advisor'
        s = json.loads((state / 'latest.json').read_text())
        at = datetime.fromisoformat(s['generated_at'])
        if at.tzinfo is None or at > now + timedelta(minutes=1):
            flag('invalid_time', 'Son kaydın saati doğrulanamadı.')
        run = json.loads((state / 'run_status.json').read_text())
        if run.get('ok') is not True or s['health'].get('errors'):
            flag('failed_cycle', 'Son V2 koşusu sağlıklı tamamlanmadı.')
        path = state / 'events.jsonl'
        if not path.is_file():
            raise ValueError('Defter eksik.')
        ledger = Ledger(path)
        # Mesai dışı early-return kaydı, kaçırılmış gündüz çevrimini asla
        # başarılı gösteremez. Eski arşiv kayıtları alan yoksa gerçek seanstır.
        checks=[e for e in ledger.events if e['kind']=='session_check' and e['data'].get('in_execution_window', True)]
        check=checks[-1] if checks else None
        if due.date().isoformat()>=cfg['start_date']:
            if check is None or datetime.fromisoformat(check['at'])<due:
                flag('missed_cycle','Beklenen işlem penceresindeki V2 koşusu arşivde yok.')
            elif check['data']['valid_quotes']<check['data']['expected_quotes']:
                flag('price_coverage','Son işlem penceresinde fiyat kapsamı veya kotasyon zamanı eksik.')
            if check and not check['data'].get('corporate_ok',True):
                flag('corporate_uncertain','Kurumsal işlem kaynağı/mutabakatı doğrulanamadı.')
            if check and check['data']['decisions']<check['data']['expected_quotes']:
                flag('decision_coverage','Bazı varlıklar karar akışına ulaşmadı.')
        for book in ('strategy', 'benchmark'):
            ledger.account(book)
        if s['health']['ledger_hash'] not in {e['hash'] for e in ledger.events}:
            flag('snapshot_ledger', 'Panel görünümü arşivdeki defterle eşleşmiyor.')
        if cfg['telegram']['enabled']:
            from .notifications import notification_key
            key = 'telegram:' + notification_key(s, at)
            if key not in ledger.keys:
                flag('notification_missing', 'Son kararın Telegram makbuzu arşivde yok.')
    except (OSError, ValueError, KeyError, TypeError):
        flag('archive_invalid', 'V2 arşivi okunamadı veya bütünlüğü doğrulanamadı.')
    if str(now.astimezone(IST).year) not in cfg['calendar']['years']:
        flag('calendar_missing', 'Bu yılın işlem takvimi eksik.')
    return {'ok': not findings, 'checked_at': now.isoformat(), 'expected_slot': due.isoformat(),
            'findings': findings, 'mode': 'observation_only'}
