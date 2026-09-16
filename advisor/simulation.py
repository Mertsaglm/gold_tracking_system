"""Geçici defterde zaman sıralı portföy simülasyonu; üretim hesabına yazmaz.

Günlük barın içindeki sıra bilinmez: iki sınır aynı gün görülürse stop önce
varsayılır. Açılış stopu aşmışsa dolum açılıştan olur. Güncel karar motorunun
nakit, lot, masraf ve risk kuralları aynen kullanılır.
"""
from datetime import datetime, timezone
from pathlib import Path
import copy
import tempfile
from collections import Counter

from . import learning, policy, benchmark, evidence, universe, engine, capsule
from .calendar import IST, trading_day
from .ledger import Ledger, fund


def quote(symbol, price, now, cfg, tradable=True):
    spread = cfg.get('historical_spread_pct', cfg['max_spread_pct']) / 100 if cfg['market']=='gold' else 0
    return {'symbol':symbol,'bid':float(price),'ask':float(price)*(1+spread),
            'reference_price':float(price),'quoted_at':now.isoformat(),'observed_at':now.isoformat(),
            'source':'günlük tarihsel referans / simülasyon', 'kind':'historical_assumption',
            'tradable':tradable}


def simulate(frame, cfg, start, end, *, membership=None, scenario=None):
    from .service import feedback, benchmark_nav
    cfg=copy.deepcopy(cfg);scenario=scenario or {};cfg['start_date']=start
    factor=float(scenario.get('cost_multiplier',1))
    if factor<1:raise ValueError('Maliyet stresi tabandan küçük olamaz.')
    for k in ('commission_rate','commission_min_try','exchange_fee_rate','slippage_bps','gold_buy_tax_rate'):
        cfg[k]*=factor
    cfg['historical_spread_pct']=cfg['max_spread_pct']*factor
    frame=frame[frame.date<=end].copy().sort_values(['symbol','date'])
    feature_cache=learning.features(frame,cfg['horizon_sessions'])
    dates=sorted(d for d in frame.date.unique() if start<=d<=end and trading_day(d,cfg))
    if not dates:raise ValueError('Simülasyon aralığında işlem günü yok.')
    membership=universe.validate(membership or [])
    model={};last_train=-10000;series=[];blocks=[];universe_missing=0;decision_counts=Counter();forecast_range=[]
    with tempfile.TemporaryDirectory(prefix='advisor-simulation-') as tmp:
        ledger=Ledger(Path(tmp)/'events.jsonl')
        for i, day in enumerate(dates):
            now=datetime.fromisoformat(day+'T10:30:00').replace(tzinfo=IST)
            previous=frame[frame.date<day]
            fund(ledger,cfg,day,now.isoformat())
            if previous.empty:continue
            asof=str(previous.date.max())
            if i-last_train>=cfg['horizon_sessions']:
                model,features=learning.train(previous,cfg,asof)
                last_train=i
            else:
                # Yalnız geriye bakan özellikler kullanılır; gelecek etiketleri karara girmez.
                features=feature_cache[feature_cache.date<day]
            latest=features.groupby('symbol').tail(1)
            live_symbols=universe.members(membership,day) if membership else set(latest[latest.in_live==1].symbol)
            if membership and not live_symbols:universe_missing+=1
            owned=set(ledger.account()['positions'])|set(ledger.account('benchmark')['positions'])
            rows=latest[latest.symbol.isin(live_symbols|owned)]
            current=frame[(frame.date==day)&frame.symbol.isin(live_symbols|owned)]
            bars={r['symbol']:r for r in current.to_dict('records')}
            skipped = scenario.get('skip_every') and (i+1)%int(scenario['skip_every'])==0
            if skipped:
                blocks.append({'date':day,'reason':'scheduled_observation_missed'});continue
            quotes={}
            for symbol,r in bars.items():
                price=r.get('open',r['close'])
                if price is None or price<=0:continue
                if day==scenario.get('gap_day'):price*=1-float(scenario.get('gap_down_pct',10))/100
                q=quote(symbol,price,now,cfg,tradable=not (symbol in scenario.get('untradable_symbols',[]) and day in scenario.get('untradable_days',[])))
                if day in scenario.get('stale_days',[]):q['quoted_at']=day+'T00:00:00+00:00'
                quotes[symbol]=q
            forecasts={}
            if model.get('ready'):
                valid=rows.dropna(subset=learning.FEATURES)
                forecasts=dict(zip(valid.symbol,learning.predict(model,valid)))
            cfg['live_gate_passed']=evidence.live(ledger,cfg)['approved']
            cfg['allowed_entry_symbols']=sorted(live_symbols)
            pre_view=policy.value_account(ledger.account(),quotes,cfg,now)
            drawdown=feedback(ledger,pre_view).get('drawdown_pct')
            cfg['risk_multiplier']=.25 if drawdown is not None and drawdown<=-cfg['learning']['max_live_drawdown_pct'] else 1
            decisions,_=engine.run(ledger,capsule.clean(rows.to_dict('records')),forecasts,model,cfg,quotes,now)
            for d in decisions:
                decision_counts[d['code']]+=1
                if d.get('forecast_pct') is not None:forecast_range.append(d['forecast_pct'])
                if d['action']=='VERİ BEKLENİYOR':blocks.append({'date':day,'symbol':d['symbol'],'reason':d['code'],'details':d['reasons']})
            benchmark.step(ledger,cfg,quotes,sorted(live_symbols),now)
            # Aynı günlük barda stop ve hedef görüldüyse iyimser sırayı seçme.
            intraday=now.replace(hour=11,minute=45)
            for symbol,p in list(ledger.account()['positions'].items()):
                bar=bars.get(symbol);q=quotes.get(symbol)
                if not bar or not q or q.get('tradable') is False:continue
                low=policy.execution_price(quote(symbol,bar['low'],intraday,cfg),cfg,'SELL')
                high=policy.execution_price(quote(symbol,bar['high'],intraday,cfg),cfg,'SELL')
                exit_price,reason=None,None
                if p.get('stop') and low<=p['stop']:
                    # Dolum kayması execution_price içinde bir kez uygulanır.
                    exit_price,reason=p['stop'],'stop'
                elif p.get('target') and high>=p['target']:
                    exit_price,reason=p['target'],'target'
                if exit_price is not None:
                    exitq=quote(symbol,exit_price,intraday,cfg)
                    if day in scenario.get('stale_days',[]):exitq['quoted_at']=q['quoted_at']
                    policy.execute(ledger,cfg,[{'symbol':symbol,'action':'SAT','code':reason}],{symbol:exitq},intraday)
            close_at=now.replace(hour=12 if day in cfg.get('calendar',{}).get('half_days',[]) else 17,minute=30)
            marks={s:quote(s,r['close'],close_at,cfg) for s,r in bars.items()}
            strategy=policy.value_account(ledger.account(),marks,cfg,close_at)
            baseline=policy.value_account(ledger.account('benchmark'),marks,cfg,close_at)
            f=feedback(ledger,strategy);bnav=benchmark_nav(ledger,baseline)
            row={'date':day,'equity_try':strategy['equity_try'],'benchmark_try':baseline['equity_try'],
                 'contributed_try':strategy['contributed_try'],'nav':f['nav'],'benchmark_nav':bnav,
                 'drawdown_pct':f['drawdown_pct'],'cash_try':strategy['cash_try']}
            series.append(row)
            if f['nav'] is not None:
                ledger.add('valuation','valuation:'+day,close_at.isoformat(),**row)
        strategy=ledger.account();baseline=ledger.account('benchmark')
        return {'start':start,'end':end,'scenario':scenario,'series':series,
                'fills':strategy['fills'],'benchmark_fills':baseline['fills'],'blocks':blocks,
                'cash_try':strategy['cash_cents']/100,'contributed_try':strategy['contributed_cents']/100,
                'fees_try':sum(f['fee_cents'] for f in strategy['fills'])/100,
                'max_drawdown_pct':min([r['drawdown_pct'] for r in series if r['drawdown_pct'] is not None],default=None),
                'evidence':evidence.live(ledger,cfg),'universe_missing_sessions':universe_missing,
                'decision_counts':dict(decision_counts),'forecast_range_pct':[min(forecast_range),max(forecast_range)] if forecast_range else None,
                'limitations':['Günlük bar yolu varsayımsal; iki sınır birlikte görülürse stop önce işlenir.',
                    'Banka makası/kayma tarihsel kotasyon değildir; maliyet varsayımıdır.',
                    'Sonradan düzeltilmiş fiyatlar ve ödeme tarihi eksik kurumsal işlemler gerçek tarihi lot/nakit akışından farklı olabilir.',
                    'Tarihli üyelik kaynağı kullanıldı; boş tarihlerde alım yok.' if membership else 'Tarihsel evren yok: güncel evren varsayımı; üstünlük kanıtı olarak kullanılamaz.'],
                'mode':'historical_paper_simulation','production_eligible':False}
