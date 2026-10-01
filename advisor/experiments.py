"""Sabit aday kataloğu; seçim geliştirme bölümünde, son bölüm yalnız sınavdır."""
import copy
from pathlib import Path
from .candidates import CATALOG, configuration
from .simulation import simulate
from .ledger import digest
from .calendar import trading_day, require_coverage


def metrics(series, start=None, end=None):
    rows = [r for r in series if r['nav'] is not None and r['benchmark_nav'] is not None and (end is None or r['date'] <= end)]
    if not rows:
        return {'excess_pct': None}
    before = [r for r in rows if start and r['date'] < start]
    chosen = [r for r in rows if start is None or r['date'] >= start]
    if not chosen:
        return {'excess_pct': None}
    base = before[-1] if before else {'nav':1., 'benchmark_nav':1.}
    last = chosen[-1]
    strategy = (last['nav']/base['nav']-1)*100
    baseline = (last['benchmark_nav']/base['benchmark_nav']-1)*100
    peak = base['nav']; drawdown = 0.
    for row in chosen:
        peak = max(peak, row['nav']); drawdown = min(drawdown, (row['nav']/peak-1)*100)
    invested=[r['invested_pct'] for r in chosen if r.get('invested_pct') is not None]
    positive_s=positive_b=0.
    previous=base
    for r in chosen:
        b=r['benchmark_nav']/previous['benchmark_nav']-1
        if b>0:
            positive_b+=b;positive_s+=r['nav']/previous['nav']-1
        previous=r
    return {'mean_invested_pct':sum(invested)/len(invested) if invested else None,
            'positive_market_capture_pct':positive_s/positive_b*100 if positive_b else None,
            'return_pct': strategy, 'benchmark_pct': baseline, 'excess_pct': strategy-baseline,
            'drawdown_pct':drawdown, 'sessions':len(chosen)}


def compare(frame, cfg, start, end, *, scenario=None):
    require_coverage(start, end, cfg)
    dates = sorted(d for d in frame.date.unique() if start <= d <= end and trading_day(d,cfg))
    if len(dates) < 100:
        raise ValueError('Ortak geliştirme/sınav için en az 100 tarih gerekli.')
    split = dates[int(len(dates)*.7)]
    specs = ({'id':'control-20-v1', 'name':'Mevcut 20 seans kontrolü', 'horizon':20, 'style':'trend'},) + CATALOG
    contract = {'catalog':specs,'start':start,'end':end,'holdout_start':split,
                'selection':'Geliştirme bölümünde masraf sonrası al-tut farkı; eşitlikte daha az gerileme.',
                'retrain_sessions':20, 'scenario':scenario or {}, 'initial_try':cfg['initial_try'],'monthly_try':cfg['monthly_try'],
                'code_hash':digest({p.name:p.read_text() for p in sorted(Path(__file__).parent.glob('*.py'))}),
                'configuration':cfg, 'data_through':str(frame.date.max()),
                'watchlist':sorted(frame.attrs.get('live_symbols', [])),
                'data_hash':str(__import__('pandas').util.hash_pandas_object(frame,index=False).sum())}
    results = []
    for spec in specs:
        c = copy.deepcopy(cfg) if spec['id']=='control-20-v1' else configuration(cfg,spec)
        # Aynı eğitim takvimi ve risk bütçesi; tek fark önceden tanımlı adaydır.
        c['research_retrain_sessions'] = 20
        run = simulate(frame,c,start,end,scenario=scenario,research=True)
        results.append(dict(spec, development=metrics(run['series'],end=dates[int(len(dates)*.7)-1]),
                            holdout=metrics(run['series'],start=split), fees_try=run['fees_try'],
                            fills=len(run['fills']), limitations=run['limitations'], series=run['series'],
                            custody=run['custody'], decision_counts=run['decision_counts'], blocks=run.get('blocks', []),
                            forecast_range_pct=run.get('forecast_range_pct')))
    eligible = [r for r in results if r['development'].get('excess_pct') is not None]
    selected = max(eligible,key=lambda r:(r['development']['excess_pct'],r['development']['drawdown_pct'])) if eligible else None
    return dict(contract=contract, contract_id=digest(contract), candidates=results,
                missing_history_symbols=sorted(set(frame.attrs.get('live_symbols', []))-set(frame.symbol)),
                selected_on_development=selected['id'] if selected else None, production_eligible=False,
                automatic_promotion=False,
                note='Bu sınav keşif amaçlıdır. Bugünkü evren/sonradan düzeltilmiş fiyatlar kullanılır; tarihsel banka kotasyonu yoktur. Son bölümdeki sonuca göre tekrar seçim yapmak yeni bir denemedir. Araştırma 20 seansta bir, ileriye dönük hat her yeni kapanışta eğitilir; sonuçlar eşdeğer değildir.')
