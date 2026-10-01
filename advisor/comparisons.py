"""Sınırlı, önceden tanımlı tek-değişken sınavları; otomatik seçim/terfi yok."""
import copy
from pathlib import Path
from . import learning
from .candidates import configuration, CATALOG
from .experiments import metrics
from .ledger import digest
from .simulation import simulate
from .calendar import trading_day, require_coverage


def plans(cfg):
    base = copy.deepcopy(cfg)
    def item(key, c, parent=None, change='kontrol', exclude=()):
        return dict(id=key, cfg=c, parent=parent, change=change, exclude=list(exclude))
    rows = [item('control', base)]
    simple = configuration(base, next(s for s in CATALOG if s['style']=='sma50'))
    rows.append(item('sma50', simple, 'control', 'Ridge yerine önceden sabit SMA50 işlem kuralı'))
    window = copy.deepcopy(base); window['learning']['window_sessions']=756
    rows.append(item('window', window, 'control', 'Yalnız 756 seans eğitim penceresi'))
    recent = copy.deepcopy(window); recent['learning']['half_life_sessions']=126
    rows.append(item('recency', recent, 'window', 'Yalnız 126 seans yarım ömür'))
    full = copy.deepcopy(recent); full['learning']['features']=list(learning.ADAPTIVE_FEATURES)
    rows.append(item('adaptive', full, 'recency', 'Altı ek özellik birlikte'))
    groups = {'pullback':['zscore20','range20'], 'short_momentum':['momentum5'],
              'volatility':['volatility_ratio'], 'relative_breadth':['relative20','breadth50']}
    for name, excluded in groups.items():
        c=copy.deepcopy(full); c['learning']['features']=[f for f in learning.ADAPTIVE_FEATURES if f not in excluded]
        rows.append(item('without_'+name,c,'adaptive','Çıkarılan özellik grubu: '+','.join(excluded)))
    short=copy.deepcopy(full);short['horizon_sessions']=5
    rows.append(item('short',short,'adaptive','Yalnız 5 seans hedefi'))
    pull=copy.deepcopy(short);pull['entry_style']='reversion'
    rows.append(item('pullback',pull,'short','Yalnız geri çekilme giriş kuralı'))
    pull_shape=copy.deepcopy(pull)
    pull_shape['learning']['features']=[f for f in learning.ADAPTIVE_FEATURES if f not in ('zscore20','range20')]
    rows.append(item('pullback_without_shape',pull_shape,'pullback','Geri çekilme giriş kuralı sabit; tahminden zscore20/range20 çıkar'))
    off=copy.deepcopy(base);off['research_regime']='none'
    rows.append(item('regime_none',off,'control','Yalnız piyasa rejimi ayarı kapalı; diğer risk sınırları aynı'))
    if cfg['market']=='bist':
        old=copy.deepcopy(base);old['research_regime']='v1'
        rows.append(item('regime_v1',old,'control','V1 sınıflandırıcısı: boyut/nakit/pozisyon politikası, V2 risk tavanlarını aşamaz'))
        for name,excluded in [('bist30',['CCOLA','CIMSA']),('without_ccola',['CCOLA']),('without_cimsa',['CIMSA'])]:
            rows.append(item(name,base,'control','Yalnız izleme/eğitim evreninden çıkar: '+','.join(excluded),excluded))
    return rows


def v1_history(con, start, end):
    """Asıl V1 classify çağrılır; eksik göstergeler yalnız bellek kopyasında yeniden hesaplanır."""
    import sqlite3
    from src import regime, indicators, util, universe
    cfg=util.load_config()
    with sqlite3.connect(':memory:') as replica:
        replica.row_factory=sqlite3.Row
        con.backup(replica)
        # Yuvarlanan göstergeler geleceğe bakmaz. SQL arşivi/üretim DB'si değişmez.
        indicators.compute_and_store(cfg,replica,tickers=universe.measure(replica),start=start)
        dates=[r[0] for r in replica.execute('SELECT DISTINCT date FROM bars_daily WHERE date>=? AND date<=? ORDER BY date',(start,end))]
        rows={d:regime.classify(cfg,replica,d) for d in dates}
    return {'rows':rows,'config':{'rejim':cfg['rejim'],'gostergeler':cfg['gostergeler']},
            'source_hash':digest({p.name:p.read_text() for p in sorted(Path(regime.__file__).parent.glob('*.py'))}),
            'note':'Orijinal V1 sınıflandırıcı. SMA50 geçmiş fiyatlardan bellek kopyasında yeniden üretildi; makro ve üyelik arşivi o günkü veri sürümünün garantisi değildir.'}


def compare(frame, cfg, start, end, regimes=None):
    require_coverage(start, end, cfg)
    dates=sorted(d for d in frame.date.unique() if start<=d<=end and trading_day(d,cfg))
    if len(dates)<100:raise ValueError('Karşılaştırma için en az 100 tarih gerekli.')
    split=dates[int(len(dates)*.7)]
    catalog=plans(cfg)
    if cfg['market']=='bist' and not regimes:raise ValueError('BIST karşılaştırmasında gerçek V1 rejim girdileri gerekli.')
    contract={'start':start,'end':end,'split':split,'plans':catalog,'retrain_sessions':20,
              'watchlist':sorted(frame.attrs.get('live_symbols',[])),
              'code_hash':digest({p.name:p.read_text() for p in sorted(Path(__file__).parent.glob('*.py'))}),
              'data_hash':str(__import__('pandas').util.hash_pandas_object(frame,index=False).sum()),
              'regime_hash':digest(regimes) if regimes else None,
              'selection':'Seçim/terfi yok; bütün karşılaştırmalar raporlanır.',
              'evaluation_status':'Keşif: bu son dönem önceki revizyonda görüldü; yeni bağımsız test değildir.'}
    results=[]
    for spec in catalog:
        c=copy.deepcopy(spec['cfg']);c['research_retrain_sessions']=20
        # Evren deneyi eğitimdeki göreli özellikleri de değiştirir; yalnız işlem listesini kırpmaz.
        excluded=set(spec['exclude']);f=frame[~frame.symbol.isin(excluded)].copy()
        f.attrs['live_symbols']=sorted(set(frame.attrs.get('live_symbols',[]))-excluded)
        scenario={'regimes':regimes['rows']} if c.get('research_regime')=='v1' else {}
        run=simulate(f,c,start,end,scenario=scenario,research=True)
        result={k:spec[k] for k in ('id','parent','change','exclude')}
        result.update(development=metrics(run['series'],end=dates[int(len(dates)*.7)-1]),
                      holdout=metrics(run['series'],start=split),series=run['series'],
                      fills=len(run['fills']),fees_try=run['fees_try'],custody=run['custody'],
                      regime_observations=run['regime_observations'], missing_history_symbols=run['missing_history_symbols'],
                      turnover_try=sum(x['notional_cents'] for x in run['fills'])/100,
                      limitations=run['limitations'])
        result.update(decision_counts=run.get('decision_counts', {}), blocks=run.get('blocks', []),
                      forecast_range_pct=run.get('forecast_range_pct'))
        results.append(result)
    by_id={r['id']:r for r in results}
    for r in results:
        if r['parent']:
            r['difference_vs_parent']={period:{key:r[period][key]-by_id[r['parent']][period][key]
                if r[period].get(key) is not None and by_id[r['parent']][period].get(key) is not None else None
                for key in ('return_pct','drawdown_pct','mean_invested_pct','positive_market_capture_pct')}
                for period in ('development','holdout')}
    return {'contract':contract,'contract_id':digest(contract),'results':results,'regimes':regimes,
            'production_eligible':False,'automatic_promotion':False,
            'notes':['Özellik grubu çıkarma farkı bağımsız nedensel etki değildir; özellikler etkileşir.',
                     'Aynı geçmişte çoklu karşılaştırma keşiftir. Parametre araması veya geçmişe göre evren seçimi yapılmaz.',
                     'V1 BIST rejimi altına taşınmadı; altında mevcut ayar ile ayarsız yöntem karşılaştırılır.']}
