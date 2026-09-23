"""Donmuş önceki model ile günlük model politikasının aynı tarihteki sınavı."""
import json
from pathlib import Path

from . import learning
from .evidence import interval
from .ledger import atomic_json


def reference(state, previous_model, current_model):
    path=Path(state)/'shadow_reference.json'
    if path.exists():
        return json.loads(path.read_text())
    model=previous_model if previous_model.get('ready') else current_model
    if not model.get('ready'):
        return None
    atomic_json(path,model)
    return model


def record(ledger, reference_model, rows, current_forecasts, now, horizon_sessions=20):
    if not reference_model or reference_model.get('horizon_sessions', 20) != horizon_sessions:
        return
    valid=rows.dropna(subset=learning.FEATURES)
    valid=valid[valid.date>=reference_model.get('label_end',reference_model.get('asof','9999'))]
    if valid.empty:
        return
    for row, value in zip(valid.to_dict('records'),learning.predict(reference_model,valid)):
        current=current_forecasts.get(row['symbol'])
        if current is None:
            continue
        key=f"shadow:{reference_model['id']}:{row['symbol']}:{row['date']}"
        if horizon_sessions != 20: key += f':horizon:{horizon_sessions}'
        ledger.add('shadow_forecast',key,now.isoformat(),symbol=row['symbol'],asof=row['date'],
                   reference_id=reference_model['id'],reference_forecast=float(value),candidate_forecast=float(current),
                   horizon_sessions=horizon_sessions)


def resolve(ledger, features, now):
    from .outcomes import targets
    lookups={}
    for e in list(ledger.events):
        if e['kind']!='shadow_forecast':
            continue
        d=e['data'];horizon=d.get('horizon_sessions',20)
        if horizon not in lookups:lookups[horizon]=targets(features,horizon)
        row=lookups[horizon].get((d['symbol'],d['asof']))
        if row is None or not isinstance(row.get('label_end'),str) or row['label_end']>now.date().isoformat():
            continue
        import math
        actual=float(row['forward_pct'])
        if not math.isfinite(actual):
            continue
        improvement=abs(d['reference_forecast']-actual)-abs(d['candidate_forecast']-actual)
        ledger.add('shadow_outcome','outcome:'+e['key'],now.isoformat(),**d,
                   end=row['label_end'],actual_pct=actual,error_improvement_pct=improvement)


def score(ledger,cfg):
    from collections import defaultdict
    groups=defaultdict(list)
    for e in ledger.events:
        if e['kind']=='shadow_outcome' and e['data'].get('horizon_sessions',20)==cfg['horizon_sessions']:
            groups[e['data']['asof']].append(e['data'])
    next_day='';values=[]
    for day, rows in sorted(groups.items()):
        if day<next_day:continue
        values.append(sum(r['error_improvement_pct'] for r in rows)/len(rows))
        next_day=max(r['end'] for r in rows)
    result=interval(values,cfg['learning'].get('min_live_periods',24))
    result['mean_error_improvement_pct']=result.pop('mean_excess_pct')
    result['note']='Pozitif fark günlük model politikasının tahmin hatasını azalttığını gösterir; işlem kârı veya otomatik terfi değildir.'
    result['automatic_promotion']=False
    return result


def portfolios(ledger,reference_model,rows,current_forecasts,model,cfg,quotes,now,event_note=None):
    """İki gölge hesap aynı para/pozisyonla başlar; ana hesap hiç etkilenmez."""
    from . import capsule, engine, policy, evidence
    from .ledger import Ledger
    if not reference_model or not model.get('ready'):
        return {'ready':False,'note':'İki model hazır olduğunda gölge hesaplar açılır.'}
    opening=next((e for e in ledger.events if e['kind']=='shadow_books_opened'),None)
    contributions=[e for e in ledger.events if e['kind']=='contribution' and e['data']['book']=='strategy']
    if not opening:
        base=ledger.account()
        value=policy.value_account(base,quotes,cfg,now)['equity_try']
        if value is None:return {'ready':False,'note':'Başlangıç değerlemesi eksik.'}
        payload=capsule.clean(base)
        for book in ('shadow_reference','shadow_candidate'):
            ledger.add('account_checkpoint','checkpoint:'+book,now.isoformat(),book=book,account=payload)
        ledger.add('shadow_books_opened','shadow-books',now.isoformat(),contributions=[e['key'] for e in contributions],
                   equity_try=value,reference_id=reference_model['id'])
        opening=ledger.events[-1]
    for e in contributions:
        if e['key'] in opening['data']['contributions']:continue
        for book in ('shadow_reference','shadow_candidate'):
            ledger.add('contribution',book+':'+e['key'],e['at'],book=book,amount_cents=e['data']['amount_cents'])
    valid=rows.dropna(subset=learning.FEATURES)
    valid=valid[valid.date>=reference_model.get('label_end',reference_model.get('asof','9999'))]
    reference_forecasts=dict(zip(valid.symbol,learning.predict(reference_model,valid))) if not valid.empty else {}
    views={}
    for book,forecast,chosen_model in (('shadow_reference',reference_forecasts,reference_model),('shadow_candidate',current_forecasts,model)):
        engine.run(ledger,capsule.clean(rows.to_dict('records')),forecast,chosen_model,cfg,quotes,now,event_note,book=book)
        views[book]=policy.value_account(ledger.account(book),quotes,cfg,now)
    previous=[e['data'] for e in ledger.events if e['kind']=='shadow_valuation']
    prior=previous[-1] if previous else None
    values={}
    for book,view in views.items():
        equity=view['equity_try']
        if equity is None:continue
        delta=view['contributed_try']-(prior['contributed_try'] if prior else ledger.account()['contributed_cents']/100)
        old_equity=prior[book+'_equity'] if prior else opening['data']['equity_try']
        values[book+'_equity']=equity
        values[book+'_nav']=(prior[book+'_nav'] if prior else 1)*(equity-delta)/old_equity if old_equity>0 else None
    if len(values)==4 and all(v is not None for v in values.values()):
        ledger.add('shadow_valuation','shadow-valuation:'+now.isoformat(),now.isoformat(),**values,
                   contributed_try=views['shadow_candidate']['contributed_try'])
    comparison=Ledger(Path('/nonexistent-shadow-comparison'))
    comparison.events=[{'kind':'valuation','at':e['at'],'data':{'nav':e['data']['shadow_candidate_nav'],'benchmark_nav':e['data']['shadow_reference_nav']}}
                       for e in ledger.events if e['kind']=='shadow_valuation']
    return {'ready':True,'reference_id':reference_model['id'],'reference_equity_try':views['shadow_reference']['equity_try'],
            'candidate_equity_try':views['shadow_candidate']['equity_try'],
            'evidence':evidence.live(comparison,cfg),'automatic_promotion':False,
            'note':'İki ayrı gölge defter, aynı başlangıç hesabı ve katkılar. Ana portföye işlem veya otomatik model değişimi yapmaz.'}
