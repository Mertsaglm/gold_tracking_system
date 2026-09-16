"""Sade karar açıklaması; sayılar aynı muhasebeden türetilir."""
from collections import Counter
from datetime import datetime, timedelta

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
    navs=[e['data']['nav'] for e in valuations if start<datetime.fromisoformat(e['at'])<=end_at and e['data'].get('nav') is not None]
    peak=before[-1]['data'].get('nav',1) if before else 1;drawdown=0
    for nav in navs:
        peak=max(peak,nav)
        drawdown=min(drawdown,(nav/peak-1)*100)
    return {'ready':True,'from':start.isoformat(),'through':end['at'],'contributions_try':delta,
            'investment_result_try':result,'fees_try':sum(f['fee_cents'] for f in fills)/100,
            'buys':sum(f['side']=='BUY' for f in fills),'sells':sum(f['side']=='SELL' for f in fills),
            'baseline_result_try':baseline,'excess_try':result-baseline if baseline is not None else None,
            'max_drawdown_pct':drawdown,'stale':(now-end_at).total_seconds()>26*3600,
            'note':'Son 7 gün, son geçerli değerlemeye kadar. Masraf net sonucun içindedir; ikinci kez çıkarılmaz.'}


def weekly_text(snapshot):
    w=snapshot.get('weekly',{})
    if not w.get('ready'):return 'V2 haftalık sonuç için değerleme bekleniyor.'
    base=f"{w['excess_try']:+.2f} TL" if w['excess_try'] is not None else 'değerleme eksik'
    return (f"{snapshot['market'].upper()} · SON 7 GÜN · SANAL\n"
            f"Eklenen para: {w['contributions_try']:.2f} TL\nYatırım sonucu: {w['investment_result_try']:+.2f} TL\n"
            f"Ödenen masraf: {w['fees_try']:.2f} TL (sonuca dahil)\nAl-tut farkı: {base}\n"
            f"İşlemler: {w['buys']} alış, {w['sells']} satış\nSon değerleme: {w['through'][:16]}")
