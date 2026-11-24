"""Sabit aday kataloğu; seçim geliştirme bölümünde, son bölüm yalnız sınavdır."""
import copy
from datetime import date, datetime, timedelta
from pathlib import Path
from . import calendar, marketdata, policy, portfolio_candidates
from .candidates import CATALOG, configuration
from .simulation import simulate
from .ledger import Ledger, digest
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


def gold_quote_timing(source, config, start, end, workspace):
    """Mühürlü banka kotasyonlarında aynı katkının iki pasif zamanlaması."""
    require_coverage(start, end, config)
    if config['market'] != 'gold' or end < start:
        raise ValueError('Altın kotasyon deneyi için geçerli tarih aralığı gerekli.')
    cfg = {**config, 'max_spread_pct': 4., 'require_next_quote': True, 'execution_phase': 'entry'}
    arms = {key: Ledger(workspace / key) for key in ('first-eligible', 'tight-then-eligible')}
    series = {key: {} for key in arms}
    wait_until = {}
    covered_days, entry_quotes, observed = set(), 0, 0
    contributions = []
    events = sorted(source.events, key=lambda event: datetime.fromisoformat(event['at']))
    for event in events:
        at = datetime.fromisoformat(event['at']).astimezone(calendar.IST)
        day = at.date().isoformat()
        if not start <= day <= end:
            continue
        data = event['data']
        if event['kind'] == 'contribution' and data['book'] == 'strategy':
            contributions.append({'at': at.isoformat(), 'cents': data['amount_cents'], 'period': data['period']})
            for key, ledger in arms.items():
                ledger.add('contribution', event['key'], at.isoformat(), book='core',
                           amount_cents=data['amount_cents'], period=data['period'])
                wait_until.setdefault(key, calendar.add_sessions(day, 3, cfg))
        if event['kind'] != 'quote_snapshot' or not contributions:
            continue
        quote = data['quotes'].get('GRAM')
        phase = calendar.phase(at, cfg)
        if phase == 'closed' or marketdata.price_problem(quote, cfg, at) is not None:
            continue
        if quote.get('kind') == 'historical_assumption':
            raise ValueError('Altın kotasyon deneyinde banka arşivi gerekli.')
        observed += 1
        if phase == 'entry' and quote.get('tradable') is not False:
            covered_days.add(day)
            entry_quotes += 1
            for key, ledger in arms.items():
                cap = 2.75 if key == 'tight-then-eligible' and day < wait_until.get(key, '') else 4.
                account = ledger.account('core')
                if account['cash_cents'] and not marketdata.spread_problem(quote, {**cfg, 'max_spread_pct': cap}):
                    trade = portfolio_candidates._trade(ledger, cfg, {'GRAM': quote}, at, 'core', 'GRAM', 'BUY',
                                                        account['cash_cents'] / 100, reason=key)
                    if trade['status'] == 'doldu':
                        wait_until.pop(key, None)
        for key, ledger in arms.items():
            value = policy.value_account(ledger.account('core'), {'GRAM': quote}, cfg, at)
            series[key][day] = {name: value[name] for name in ('equity_try', 'cash_try', 'contributed_try')}
    if not contributions or not observed:
        raise ValueError('Katkı ve geçerli banka kotasyonu bulunamadı.')
    expected = sum(calendar.trading_day(date.fromisoformat(start) + timedelta(days=i), cfg)
                   for i in range((date.fromisoformat(end) - date.fromisoformat(start)).days + 1))
    reports = {}
    for key, ledger in arms.items():
        nav = peak = 1.
        worst = previous_value = previous_contributed = 0.
        records = []
        for day, row in series[key].items():
            denominator = previous_value + row['contributed_try'] - previous_contributed
            nav *= row['equity_try'] / denominator
            peak = max(peak, nav)
            worst = min(worst, nav / peak - 1)
            previous_value, previous_contributed = row['equity_try'], row['contributed_try']
            records.append({'date': day, **row, 'nav': nav})
        account = ledger.account('core')
        reports[key] = {**records[-1], 'twr_pct': (nav - 1) * 100, 'max_drawdown_pct': worst * 100,
                        'fees_try': sum(f['fee_cents'] for f in account['fills']) / 100,
                        'grams': str(account['positions'].get('GRAM', {}).get('quantity', 0)),
                        'buys': len(account['fills']), 'buy_days': [f['at'][:10] for f in account['fills']],
                        'series': records, 'ledger_hash': ledger.root_hash}
    return {'status': 'offline banka kotasyonu deneyi', 'start': start, 'end': end, 'source_hash': source.root_hash,
            'expected_sessions': expected, 'entry_sessions_observed': len(covered_days),
            'valid_entry_quotes': entry_quotes, 'contributions': contributions, 'arms': reports,
            'protocol': {'first_cap_pct': 4., 'tight_cap_pct': 2.75, 'wait_sessions': 3,
                         'gold_buy_tax_rate': cfg['gold_buy_tax_rate'], 'execution': 'sonraki taze banka kotasyonu'},
            'automatic_promotion': False,
            'limitations': 'Gözlem boşlukları, kişisel İşCep fiyatı ve gerçek dolum bilinmiyor. Ortak gün sonu son geçerli banka fiyatıyla net değerleme.'}
