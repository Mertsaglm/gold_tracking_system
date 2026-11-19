"""Ayrı workflow'dan salt-okur gözlem: kendi baktığı süreci kilitlemez."""
from datetime import datetime, timedelta
import json
from pathlib import Path

from .calendar import IST, load, trading_day, window
from .ledger import Ledger
from .accounts import state_path
from .marketdata import price_problem


def expected_slot(now, cfg):
    cutoff = now.astimezone(IST) - timedelta(minutes=cfg.get('watchdog_grace_minutes', 90))
    for offset in range(370):
        day = cutoff.date() - timedelta(days=offset)
        if not trading_day(day, cfg):
            continue
        start, end = window(day, cfg, 'observation')
        slot = start.replace(minute=17, second=0, microsecond=0)
        slots = []
        while slot <= end:
            if slot <= cutoff:
                slots.append(slot)
            slot += timedelta(minutes=cfg.get('cycle_interval_minutes',30 if 'observation_window' in cfg else 60))
        if slots:
            return slots[-1]
    raise ValueError('Beklenen işlem aralığı bulunamadı.')


def cycle_evidence(snapshot, ledger):
    """En son karar ile kalıcı fiyat, tahmin ve Telegram kayıtlarını gösterir."""
    at = snapshot['generated_at']
    day = snapshot.get('analysis_date')
    decisions = snapshot.get('decisions', ())
    forecast_symbols = {d['symbol'] for d in decisions if d.get('forecast_pct') is not None}
    model_id = snapshot.get('learning', {}).get('id')
    archived = [e['data'] for e in ledger.events if e['kind'] == 'forecast'
                and day is not None and e['data']['asof'] == day and e['data']['symbol'] in forecast_symbols]
    delivery = next((e['data'] for e in reversed(ledger.events) if e['kind'] == 'notification'
                     and type(e['data'].get('message_id')) is int), None)
    quotes = list(snapshot.get('quotes', {}).values())
    return {
        'cycle_at': at, 'analysis_date': day,
        'quote_sources': sorted({q['source'] for q in quotes if q.get('source')}),
        'quote_coverage': snapshot['health'].get('quote_coverage'),
        'expected_quotes': snapshot['health'].get('expected_quotes'),
        'model_id': model_id,
        'forecast_symbols': len(forecast_symbols),
        'archived_forecast_symbols': len({d['symbol'] for d in archived}),
        'matching_model_forecast_symbols': len({d['symbol'] for d in archived if d.get('model_id') == model_id})
        if model_id else 0,
        'ledger_hash': snapshot['health']['ledger_hash'],
        'telegram': {**{k: delivery.get(k) for k in ('message_id', 'snapshot_at', 'report_day')},
                     'exact_cycle': delivery.get('snapshot_at') == at} if delivery else None,
    }


def inspect(root, now):
    from .service import configuration
    root = Path(root)
    cfg = configuration(root)
    cfg['calendar'] = load(root)
    due = expected_slot(now, cfg)
    if not (state_path(root, cfg) / 'events.jsonl').exists() and due.date().isoformat() < cfg['start_date']:
        return {'ok':True, 'checked_at':now.isoformat(), 'expected_slot':due.isoformat(),
                'findings':[], 'initializing':True, 'mode':'observation_only'}
    findings = []
    evidence = None
    def flag(code, message):
        findings.append({'code': code, 'message': message})
    try:
        state = state_path(root, cfg)
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
        checks=[e for e in ledger.events if e['kind']=='session_check' and e['data'].get('in_observation_window', e['data'].get('in_execution_window', True))]
        check=checks[-1] if checks else None
        if due.date().isoformat()>=cfg['start_date']:
            if check is None or datetime.fromisoformat(check['at'])<due:
                flag('missed_cycle','Beklenen işlem penceresindeki V2 koşusu arşivde yok.')
            elif check['data']['valid_quotes']<check['data']['expected_quotes']:
                flag('price_coverage','Son işlem penceresinde fiyat kapsamı veya kotasyon zamanı eksik.')
            # Kapanış değerlemesi, gün içinde pozisyonların izlenmiş olduğunu göstermez.
            opening, closing = window(due.date(), cfg)
            if now >= closing and not any(
                e['data'].get('in_execution_window', True)
                and opening <= datetime.fromisoformat(e['at']) < closing
                for e in reversed(checks)
            ):
                flag('no_execution_cycle', f'{due.date()}: işlem saatlerinde arşivlenmiş V2 çevrimi yok.')
            local_now = now.astimezone(IST)
            if trading_day(local_now.date(), cfg) and local_now.date().isoformat() >= cfg['start_date']:
                start, end = window(local_now.date(), cfg, 'observation')
                gap = cfg.get('watchdog_max_gap_minutes',45)
                required = min(local_now, end) - timedelta(minutes=gap)
                if required >= start and (check is None or datetime.fromisoformat(check['at']) < required):
                    flag('cycle_gap', f'İşlem penceresinde son V2 çevrimi {gap} dakikadan eski.')
            if check and not check['data'].get('corporate_ok',True):
                flag('corporate_uncertain','Kurumsal işlem kaynağı/mutabakatı doğrulanamadı.')
            if check and check['data']['decisions']<check['data']['expected_quotes']:
                flag('decision_coverage','Bazı varlıklar karar akışına ulaşmadı.')
            if check and check['data'].get('analysis_issues'):
                flag('analysis_coverage', 'Eksik veya beklenen kapanışın gerisinde analiz: ' + ', '.join(check['data']['analysis_issues']))
            if check and check['data'].get('data_blocked_symbols'):
                flag('decision_data', 'Karar girdisi doğrulanamayan varlıklar: ' + ', '.join(check['data']['data_blocked_symbols']))
        for book in ('strategy', 'benchmark'):
            ledger.account(book)
        if s['health']['ledger_hash'] not in {e['hash'] for e in ledger.events}:
            flag('snapshot_ledger', 'Panel görünümü arşivdeki defterle eşleşmiyor.')
        if cfg['telegram']['enabled']:
            from .notifications import closing_day, delivered
            require_closing = s.get('monitoring', {}).get('closing_report_expected', False)
            if not delivered(ledger, s, require_closing=require_closing):
                if require_closing and closing_day(s, at):
                    flag('closing_report_missing', 'Gün sonu Telegram raporu makbuzu arşivde yok.')
                else:
                    flag('notification_missing', 'Son kararın Telegram makbuzu arşivde yok.')
        evidence = cycle_evidence(s, ledger)
    except (OSError, ValueError, KeyError, TypeError):
        flag('archive_invalid', 'V2 arşivi okunamadı veya bütünlüğü doğrulanamadı.')
    if str(now.astimezone(IST).year) not in cfg['calendar']['years']:
        flag('calendar_missing', 'Bu yılın işlem takvimi eksik.')
    return {'ok': not findings, 'checked_at': now.isoformat(), 'expected_slot': due.isoformat(),
            'findings': findings, 'mode': 'observation_only', 'evidence': evidence}
