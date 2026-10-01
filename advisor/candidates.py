"""Önceden tanımlı adaylar: ayrı para, ayrı vade, aynı maliyet; otomatik terfi yok."""
import copy
import json
from pathlib import Path
import pandas as pd

from . import learning, engine, policy, outcomes, evidence, benchmark, capsule, costs, risk, corporate
from .calendar import IST
from .ledger import Ledger, atomic_json, digest, fund

CATALOG = (
    {'id': 'sma50-v1', 'name': 'Basit 50 seans trendi', 'horizon': 20, 'style': 'sma50'},
    {'id': 'recent-20-v1', 'name': 'Yakın döneme ağırlık / 20 seans', 'horizon': 20, 'style': 'trend'},
    {'id': 'recent-5-v1', 'name': 'Yakın döneme ağırlık / 5 seans', 'horizon': 5, 'style': 'trend'},
    {'id': 'reversion-5-v1', 'name': 'Sınırlı geri çekilme / 5 seans', 'horizon': 5, 'style': 'reversion'},
)


def configuration(base, spec):
    cfg = copy.deepcopy(base)
    cfg['horizon_sessions'] = spec['horizon']
    cfg['entry_style'] = spec['style']
    if spec['style'] == 'sma50':
        cfg['strategy_kind'] = 'sma50'
    else:
        cfg['learning'].update(feature_set='adaptive_v1', half_life_sessions=126, window_sessions=756)
    return cfg


def owned(state):
    symbols = set()
    for spec in CATALOG:
        path = Path(state) / 'candidates' / spec['id'] / 'events.jsonl'
        if path.exists():
            ledger = Ledger(path)
            for book in ('strategy', 'benchmark'):
                symbols.update(ledger.account(book)['positions'])
    return symbols


def cycle(state, frame, base, quotes, now, actions=()):
    from .service import feedback, benchmark_nav
    day = now.astimezone(IST).date().isoformat()
    asof = str(frame.date.max())
    views = []
    for spec in CATALOG:
        cfg = configuration(base, spec)
        path = Path(state) / 'candidates' / spec['id']
        ledger = Ledger(path / 'events.jsonl')
        contract = {k: cfg[k] for k in ('start_date', 'initial_try', 'monthly_try', 'horizon_sessions')}
        contract.update(spec=spec, learning=cfg['learning'])
        contract['decision_policy'] = {k:cfg.get(k) for k in ('max_positions','max_position_pct','risk_per_trade_pct',
            'minimum_cash_pct','min_expected_net_pct','min_net_reward_risk','max_portfolio_risk_pct',
            'max_positions_per_sector','adaptive_risk','entry_window','execution_window','require_next_quote')}
        prior = next((e['data'] for e in ledger.events if e['kind'] == 'candidate_contract'), None)
        if prior is not None and prior != contract:
            raise ValueError('Aday politikası geçmişin üstüne değiştirilemez; yeni aday kimliği gerekli.')
        ledger.add('candidate_contract', 'contract', now.isoformat(), **contract)
        fund(ledger, cfg, day, now.isoformat())
        fingerprint = digest({'frame': str(pd.util.hash_pandas_object(frame, index=False).sum()),
                              'learning': Path(learning.__file__).read_text(), 'contract': contract})
        model_path = path / 'model.json'
        model = json.loads(model_path.read_text()) if model_path.exists() else {}
        if model.get('fingerprint') != fingerprint:
            model, features = learning.train(frame, cfg, asof)
            model['fingerprint'] = fingerprint
            atomic_json(model_path, model)
        else:
            features = learning.features(frame, cfg['horizon_sessions'])
        local_blocks = corporate.reconcile(ledger, actions, cfg, now)
        cfg['blocked_symbols'] = dict(cfg.get('blocked_symbols', {}), **local_blocks)
        symbols = set(cfg['allowed_entry_symbols']) | set(ledger.account()['positions']) | set(ledger.account('benchmark')['positions'])
        rows = features[features.symbol.isin(symbols)].groupby('symbol').tail(1)
        missing = symbols - set(rows.symbol)
        if missing:
            rows = pd.concat([rows, pd.DataFrame([{'symbol':s, 'date':asof, 'close':float('nan'),
                                                  'quality_ok':False} for s in sorted(missing)])], ignore_index=True)
        outcomes.resolve(ledger, features, cfg, now)
        score = outcomes.calibration(ledger, cfg)
        forecasts = {}
        if model.get('ready') and model.get('kind') != 'sma50':
            valid = rows.dropna(subset=model['features'])
            valid = valid[(valid.date == cfg['expected_analysis_date']) & valid.quality_ok]
            forecasts = dict(zip(valid.symbol, learning.predict(model, valid).tolist()))
        raw = dict(forecasts)
        forecasts = {s: v - score['correction_pct'] for s, v in forecasts.items()}
        before = policy.value_account(ledger.account(), quotes, cfg, now)
        fb = feedback(ledger, before)
        cfg['live_gate_passed'] = evidence.live(ledger, cfg)['approved'] and fb['roundtrips'] >= cfg['learning']['min_live_roundtrips']
        cfg['risk_multiplier'] = risk.control(rows, fb, cfg)['multiplier']
        if (fb.get('drawdown_pct') or 0) <= -cfg['learning']['max_live_drawdown_pct']:
            cfg['risk_multiplier'] *= .25
        cfg['risk_multiplier'] *= base.get('event_risk_multiplier', 1)
        records = capsule.clean(rows.to_dict('records'))
        context = capsule.inputs(ledger, records, forecasts, model, cfg, quotes, now, None)
        decisions, fills = engine.run(ledger, records, forecasts, model, cfg, quotes, now)
        receipt = capsule.save(path, context, decisions)
        ledger.add('decision_capsule', 'capsule:' + receipt['id'], now.isoformat(), **receipt)
        outcomes.record(ledger, decisions, raw, now)
        benchmark.step(ledger, cfg, quotes, cfg['allowed_entry_symbols'], now)
        custody = costs.accrue(ledger, cfg, quotes, now)
        view = policy.value_account(ledger.account(), quotes, cfg, now)
        baseline = policy.value_account(ledger.account('benchmark'), quotes, cfg, now)
        fb = feedback(ledger, view)
        if view['valuation_complete']:
            ledger.add('valuation', 'valuation:' + now.isoformat(), now.isoformat(),
                       equity_try=view['equity_try'], contributed_try=view['contributed_try'], nav=fb['nav'],
                       benchmark_try=baseline['equity_try'], benchmark_nav=benchmark_nav(ledger, baseline))
        result = dict(spec, strategy=view, benchmark=baseline, feedback=fb, scorecard=score,
                      model_id=model.get('id'), ready=model.get('ready', False), evaluation=model.get('evaluation'),
                      evidence=evidence.live(ledger, cfg), custody=custody, automatic_promotion=False,
                      status='Ayrı sanal sınav; üstünlük kanıtlanmadı.', generated_at=now.isoformat())
        ledger.save()
        atomic_json(path / 'latest.json', result)
        views.append(result)
    return views
