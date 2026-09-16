"""Aynı piyasa dönemini çoğaltmadan eşleştirilmiş başarı ölçümü."""
import math
import statistics

from .calendar import IST, add_sessions
from datetime import datetime


def interval(values, minimum=24):
    n = len(values)
    mean = statistics.mean(values) if n else None
    se = statistics.stdev(values) / math.sqrt(n) if n > 1 else None
    # Küçük örneklemde normal 1.96 katsayısından daha muhafazakâr t yaklaşımı.
    z = 1.96
    critical = z + (z**3 + z)/(4*(n-1)) + (5*z**5+16*z**3+3*z)/(96*(n-1)**2) if n > 1 else None
    lower = mean-critical*se if se is not None else None
    return {'periods':n,'mean_excess_pct':mean,'lower_95_pct':lower,
            'upper_95_pct':mean+critical*se if se is not None else None,
            'minimum_periods':minimum,'approved':n>=minimum and lower is not None and lower>0,
            'method':'Örtüşmeyen dönemlerde eşleştirilmiş fark; yaklaşık t güven aralığı.'}


def live(ledger, cfg):
    daily = {}
    for e in ledger.events:
        d=e['data']
        if e['kind']=='valuation' and d.get('nav') is not None and d.get('benchmark_nav') is not None:
            day=datetime.fromisoformat(e['at']).astimezone(IST).date().isoformat()
            daily[day]=d
    periods=[]; start=None
    for day,d in sorted(daily.items()):
        if start is None:
            start=(day,d);continue
        if day < add_sessions(start[0],cfg['horizon_sessions'],cfg):
            continue
        if start[1]['nav']>0 and start[1]['benchmark_nav']>0:
            excess=(d['nav']/start[1]['nav']-d['benchmark_nav']/start[1]['benchmark_nav'])*100
            periods.append({'start':start[0],'end':day,'excess_pct':excess})
        start=(day,d)
    result=interval([p['excess_pct'] for p in periods],cfg['learning'].get('min_live_periods',24))
    result['series']=periods
    result['status']='bağımsız sanal kanıt yeterli' if result['approved'] else 'bağımsız sanal kanıt yetersiz'
    return result
