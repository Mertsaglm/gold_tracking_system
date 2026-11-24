"""Sade karar açıklaması; sayılar aynı muhasebeden türetilir."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
import sqlite3

from .ledger import cents
from .policy import fee


def enrich(decisions, ledger, cfg, previous_decisions):
    previous={d['symbol']:d for d in previous_decisions}
    positions=ledger.account()['positions']
    for d in decisions:
        old=previous.get(d['symbol'])
        changes=[]
        if old:
            for field,label in (('action','Karar'),('code','Gerekçe'),('model_id','Model sürümü'),('price','Fiyat referansı')):
                if old.get(field)!=d.get(field):changes.append({'field':field,'label':label,'before':old.get(field),'after':d.get(field)})
        d['change']={'previous_action':old.get('action') if old else None,'items':changes,'first':old is None}
        ex=d.get('execution');p=positions.get(d['symbol'])
        qty=float(ex['quantity']) if ex else float(p['quantity']) if p else None
        px=ex['price'] if ex else d.get('price')
        stop,target=d.get('stop'),d.get('target')
        paid=fee(cfg,qty*px,'BUY') if qty and px and (not ex or d['action']=='AL') else 0
        cost=cents(qty*px)+paid if qty and px else None
        if p and not ex:cost=p['cost_cents']
        stop_loss=max(0,cost-cents(qty*stop)+fee(cfg,qty*stop,'SELL'))/100 if cost and stop else None
        target_gain=(cents(qty*target)-fee(cfg,qty*target,'SELL')-cost)/100 if cost and target else None
        d['detail']={'quantity':ex['quantity'] if ex else str(p['quantity']) if p else None,'notional_try':qty*px if ex and qty and px else cost/100 if cost is not None else None,
                     'fee_try':ex['fee_try'] if ex else None,'stop_risk_try':stop_loss if d['action']!='SAT' else None,'target_net_try':target_gain if d['action']!='SAT' else None,
                     'basis':'gerçekleşen sanal işlem; alış maliyetinden risk' if ex else 'eldeki miktarın kayıtlı maliyeti' if p else 'işlem yapılmadı',
                     'note':'Stop/hedef dolumu garanti değildir; fiyat boşluğu zararı büyütebilir.'}
    return decisions


def funnel(decisions):
    counts=Counter()
    for d in decisions:
        code=d['code']
        group=('veri' if d['action']=='VERİ BEKLENİYOR' else
               'işlem' if d.get('execution') else 'elde tutma' if d['action']=='TUT' else
               'bütçe/risk' if code in {'budget','capacity','sector_cap','same_day_exit','sized_reward_risk','portfolio_risk'} else
               'model' if d.get('forecast_pct') is None else 'fırsat koşulları')
        counts[group]+=1
    return {'total':len(decisions),'groups':dict(counts),'codes':dict(Counter(d['code'] for d in decisions))}


def collection(ledger, cfg, now):
    from . import calendar

    local = now.astimezone(calendar.IST)
    interval = timedelta(minutes=cfg.get('cycle_interval_minutes', 30))
    days = {}
    for offset in range(6, -1, -1):
        day = local.date() - timedelta(days=offset)
        if not calendar.trading_day(day, cfg):
            continue
        opening, closing = calendar.window(day, cfg, 'observation')
        slots = {}
        while opening < closing and opening <= local:
            slots[opening.isoformat()] = {'state': 'kayıt yok' if min(opening + interval, closing) <= local else 'açık slot'}
            opening += interval
        days[day.isoformat()] = slots
    for event in ledger.events:
        if event['kind'] != 'session_check' or not event['data'].get('in_observation_window'):
            continue
        at = datetime.fromisoformat(event['at']).astimezone(calendar.IST)
        slots = days.get(at.date().isoformat())
        if not slots or calendar.phase(at, cfg) == 'closed':
            continue
        data = event['data']
        if data.get('phase', 'entry' if data.get('in_execution_window') else 'valuation') == 'valuation' and calendar.phase(at, cfg) != 'valuation':
            continue
        opening, _ = calendar.window(at.date(), cfg, 'observation')
        key = (opening + (at - opening) // interval * interval).isoformat()
        if key not in slots or at > local:
            continue
        row = slots[key]
        row['first_observed_at'] = min(row.get('first_observed_at', at.isoformat()), at.isoformat())
        if at.isoformat() < row.get('latest_observed_at', ''):
            continue
        valid, expected = data['valid_quotes'], data['expected_quotes']
        row.update(latest_observed_at=at.isoformat(), valid=valid, expected=expected,
                   state='tam fiyat' if valid == expected and expected > 0 else 'kısmi fiyat' if valid else 'geçerli fiyat yok',
                   source_failure=data.get('source_failure'))
    return [{'day': day, 'slots': [{'at': stamp, **row} for stamp, row in slots.items()]} for day, slots in days.items()]


def weekly(ledger, now):
    start=now-timedelta(days=7)
    valuations=[e for e in ledger.events if e['kind']=='valuation' and datetime.fromisoformat(e['at'])<=now]
    if not valuations:return {'ready':False,'note':'Haftalık sonuç için değerleme yok.'}
    end=valuations[-1];end_at=datetime.fromisoformat(end['at'])
    before=[e for e in valuations if datetime.fromisoformat(e['at'])<=start]
    base=before[-1]['data'] if before else {'equity_try':0,'contributed_try':0,'benchmark_try':0}
    current=end['data'];delta=current['contributed_try']-base['contributed_try']
    result=current['equity_try']-base['equity_try']-delta
    baseline=(current['benchmark_try']-base['benchmark_try']-delta
              if current.get('benchmark_try') is not None and base.get('benchmark_try') is not None else None)
    fills=[e['data'] for e in ledger.events if e['kind']=='fill' and e['data']['book']=='strategy' and start<datetime.fromisoformat(e['at'])<=end_at]
    account_fees=sum(e['data']['amount_cents'] for e in ledger.events if e['kind']=='account_fee' and e['data']['book']=='strategy' and start<datetime.fromisoformat(e['at'])<=end_at)
    navs=[e['data']['nav'] for e in valuations if start<datetime.fromisoformat(e['at'])<=end_at and e['data'].get('nav') is not None]
    peak=before[-1]['data'].get('nav',1) if before else 1;drawdown=0
    for nav in navs:
        peak=max(peak,nav)
        drawdown=min(drawdown,(nav/peak-1)*100)
    return {'ready':True,'from':start.isoformat(),'through':end['at'],'contributions_try':delta,
            'investment_result_try':result,'fees_try':(sum(f['fee_cents'] for f in fills)+account_fees)/100,
            'buys':sum(f['side']=='BUY' for f in fills),'sells':sum(f['side']=='SELL' for f in fills),
            'baseline_result_try':baseline,'excess_try':result-baseline if baseline is not None else None,
            'max_drawdown_pct':drawdown,'stale':(now-end_at).total_seconds()>26*3600,
            'note':'Son 7 gün, son geçerli değerlemeye kadar. Masraf net sonucun içindedir; ikinci kez çıkarılmaz.'}


def weekly_text(snapshot):
    from .calendar import IST

    w=snapshot.get('weekly',{})
    if not w.get('ready'):return 'V2 haftalık sonuç için değerleme bekleniyor.'
    base=f"{w['excess_try']:+.2f} TL" if w['excess_try'] is not None else 'değerleme eksik'
    passive=w.get('baseline_result_try')
    passive_text=f'{passive:+.2f} TL' if passive is not None else 'değerleme eksik'
    through = datetime.fromisoformat(w['through']).astimezone(IST).strftime('%d.%m.%Y %H.%M')
    return (f"{snapshot['market'].upper()} · SON 7 GÜN · SANAL\n"
            f"Eklenen para: {w['contributions_try']:.2f} TL\nYatırım sonucu: {w['investment_result_try']:+.2f} TL\n"
            f"Ödenen masraf: {w['fees_try']:.2f} TL (sonuca dahil)\n"
            f"Pasif yatırım sonucu: {passive_text}\nAktif eksi pasif: {base}\n"
            f"İşlemler: {w['buys']} alış, {w['sells']} satış\nSon değerleme: {through} İstanbul"
            + ('\n\n' + '\n'.join(snapshot['research_lines']) if snapshot.get('research_lines') else ''))


def weekly_research(root, state, ledger, cfg, now):
    """Son haftanın olgunlaşan fırsatları, ayrı hesapların eş bütçeli kıyası."""
    from . import calendar, history
    from .decision_activity import measure, summarize_outcomes

    cfg = {**cfg, 'calendar': calendar.load(root)}
    today = now.astimezone(calendar.IST).date()
    last_week = (today - timedelta(days=7)).isoformat()
    start = max(cfg['start_date'], (today - timedelta(days=90)).isoformat())
    try:
        latest = json.loads((state / 'latest.json').read_text())
    except (OSError, ValueError):
        latest = {}
    lines = ['ARAŞTIRMA · SANAL']
    experiments = latest.get('portfolio_experiments', {})
    lines.append('Çekirdek/taktik · ' + experiments.get('status', 'görünüm bekleniyor'))
    for arm in (experiments.get('comparison') or {}).get('arms', []):
        paired = arm.get('vs_passive')
        if paired is not None:
            lines.append(f"{arm['id']} · pasife göre {paired['wealth_difference_try']:+.0f} TL, "
                         f"{paired['twr_difference_pct']:+.2f} puan · {arm['sessions']} seans")
    candidates = []
    for arm in latest.get('candidates', []):
        active, passive = arm['strategy'], arm['benchmark']
        if (active.get('equity_try') is not None and passive.get('equity_try') is not None
                and active['contributed_try'] == passive['contributed_try']):
            candidates.append(f"{arm['id']} {active['equity_try'] - passive['equity_try']:+.0f}")
    if candidates:
        lines.append('İlk günden aktif eksi pasif (TL) · ' + ', '.join(candidates))
    momentum = latest.get('forward_momentum', {})
    if momentum:
        lines.append('İleri momentum · ' + momentum['status'])
        passive = momentum.get('benchmark', {}).get('equity_try')
        active = momentum.get('strategy', {}).get('equity_try')
        if active is not None and passive is not None:
            lines.append(f'İleri momentum, başlangıçtan aktif eksi pasif {active - passive:+.0f} TL')

    try:
        corporate_days = defaultdict(set)
        if cfg['market'] == 'bist':
            with history.connection(root, 'bist') as con:
                for symbol, day in con.execute('SELECT ticker,date FROM corporate_actions WHERE date BETWEEN ? AND ?',
                                               (start, today.isoformat())):
                    corporate_days[symbol].add(date.fromisoformat(day))
        activity = measure(ledger, cfg, start=start, through=today.isoformat(),
                           budget=100_000, corporate_days=corporate_days)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        return lines + [f'BEKLE ölçümü alınamadı · {type(exc).__name__}.', 'Sırada · Ölçüm girdisini doğrula.']

    due = [row for row in activity['outcomes'] if row['maturity'] and last_week < row['maturity'] <= today.isoformat()]
    groups = summarize_outcomes(due)
    for code, group in groups.items():
        counts = group['statuses']
        total = sum(counts.values())
        scored = counts.get('measured', 0)
        no_price = counts.get('no_entry_quote', 0) + counts.get('no_maturity_quote', 0)
        net = group['mean_net_pct']
        line = f'BEKLE {code} · ölçülen {scored}/{total}, fiyat eksik {no_price}'
        if net is not None:
            line += f", ort. net {net:+.2f}%, nakit üstü {group['beat_cash']}/{scored}"
            if group['passive_comparable']:
                line += f", pasif üstü {group['beat_passive']}/{group['passive_comparable']}"
            line += f" · {group['non_overlapping_periods']} örtüşmeyen pencere"
        lines.append(line)
    if not groups:
        lines.append('BEKLE · Bu hafta vadesi gelen ölçülebilir karar kohortu yok.')
    measured = [g for g in groups.values() if g['mean_net_pct'] is not None]
    if measured and all(g['mean_net_pct'] <= 0 for g in measured):
        lines.append('Öğrenilen · Ölçülen ret gruplarının ortalaması nakdi geçmedi.')
    elif measured:
        lines.append('Öğrenilen · Bazı ret gruplarında nakit üstü ortalama var. Eş portföy sınavı gerekli.')
    else:
        lines.append('Öğrenilen · Bu haftanın ekonomik etkisi ölçülemedi.')
    if any(g['statuses'].get('no_maturity_quote') for g in groups.values()):
        lines.append('Sırada · Eksik vade fiyatı kapsamını ölç ve aynı hipotezi yeni kohortta izle.')
    elif experiments.get('status') == 'T0 bekleniyor':
        lines.append('Sırada · Ortak T0 uygunluğunu ölç, bağımsız rakipleri izlemeyi sürdür.')
    else:
        lines.append('Sırada · Yeni kohortu aynı maliyetle eş pasif kola karşı izle.')
    return lines
