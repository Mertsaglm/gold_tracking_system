"""V2 koşusu: arşiv → model → güncel fiyat → karar → sanal defter → görünüm."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import history, learning, marketdata, news, policy, outcomes, corporate as corporate_module
from .ledger import Ledger, atomic_json, cents, digest, fund, locked

IST = ZoneInfo("Europe/Istanbul")


def configuration(root):
    cfg = json.loads((root / "advisor/config.json").read_text(encoding="utf-8"))
    if cfg["market"] not in {"bist", "gold"} or cfg["initial_try"] <= 0 or cfg["monthly_try"] < 0:
        raise ValueError("Geçersiz portföy yapılandırması.")
    if not 0 < cfg["risk_per_trade_pct"] <= 2 or not 0 < cfg["max_position_pct"] <= 100:
        raise ValueError("Risk sınırı geçersiz.")
    return cfg


def holidays(root):
    p = root / "holidays_tr.yaml"
    if not p.exists():
        p = root / 'holidays.yaml'
    if not p.exists():
        return []
    # Her iki eski projenin takvimi farklı biçim kullanır; tarihli tüm kayıtları al.
    import re
    return sorted(set(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", p.read_text(encoding="utf-8"))))


def benchmark_step(ledger, cfg, quotes, symbols, now):
    """Aynı katkı ve banka maliyetiyle ayda bir eşit tutar al-tut tabanı."""
    if not symbols or any(marketdata.usable(quotes.get(s), cfg, now, cfg.get("holidays", ())) or s in cfg.get('blocked_symbols', {}) for s in symbols):
        return
    for event in list(ledger.events):
        d = event["data"]
        if event["kind"] != "contribution" or d.get("book") != "benchmark":
            continue
        key = "benchmark:allocation:" + event["key"]
        if key in ledger.keys:
            continue
        budget = d["amount_cents"] // len(symbols)
        for symbol in symbols:
            px = policy.execution_price(quotes[symbol], cfg, "BUY")
            qty = policy.quantity_for(budget, px, cfg)
            if not qty:
                continue
            ledger.add("fill", key + ":" + symbol, now.isoformat(), book="benchmark", symbol=symbol,
                       side="BUY", quantity=str(qty), price=px, notional_cents=cents(float(qty) * px),
                       fee_cents=policy.fee(cfg, float(qty) * px, "BUY"), quote=quotes[symbol],
                       reason="monthly_buy_hold", decision_key=key, stop=None, target=None, deadline=None)
        ledger.add("benchmark_allocation", key, now.isoformat(), contribution_key=event["key"])
    ledger.account("benchmark")


def feedback(ledger, view):
    snapshots = [e["data"] for e in ledger.events if e["kind"] == "valuation"]
    current = view.get("equity_try")
    if current is None:
        return {"nav": None, "drawdown_pct": None, "roundtrips": 0, "status": "değerleme eksik"}
    previous = snapshots[-1] if snapshots else None
    nav = current / view['contributed_try'] if view['contributed_try'] else 1.0
    if previous and previous["equity_try"] > 0:
        delta = view["contributed_try"] - previous["contributed_try"]
        nav = previous["nav"] * (current - delta) / previous["equity_try"]
    peak = max([nav, 1.0] + [s["nav"] for s in snapshots])
    drawdown = (nav / peak - 1) * 100
    trades = [x for x in view["fills"] if x["side"] == "SELL"]
    return {"nav": nav, "drawdown_pct": drawdown, "roundtrips": len(trades),
            "status": "canlı sanal sonuçlar birikiyor", "twr_pct": (nav - 1) * 100}


def benchmark_nav(ledger, view):
    """Al-tut getirisi de katkılardan arındırılır; grafik kırpılması onu sıfırlamaz."""
    if view['equity_try'] is None:
        return None
    nav, previous = 1.0, None
    rows = [e['data'] for e in ledger.events if e['kind'] == 'valuation']
    rows.append({'benchmark_try': view['equity_try'], 'contributed_try': view['contributed_try']})
    for row in rows:
        equity = row.get('benchmark_try')
        if equity is None:
            continue
        contribution = row['contributed_try']
        if previous and previous['benchmark_try'] > 0:
            nav *= (equity - (contribution - previous['contributed_try'])) / previous['benchmark_try']
        else:
            nav = equity / contribution if contribution else 1.0
        previous = row
    return nav


def cycle(root, *, database=None, now=None, quotes=None, offline=False, notify=False):
    root = Path(root).resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Koşu zamanı saat dilimi içermeli.")
    cfg = configuration(root)
    cfg["holidays"] = holidays(root)
    state = root / "data/advisor"
    with locked(state / ".lock"):
        ledger = Ledger(state / "events.jsonl")
        budget_signature = {k: cfg[k] for k in ("market", "start_date", "initial_try", "monthly_try")}
        origin = next((e["data"] for e in ledger.events if e["kind"] == "account_opened"), None)
        if origin and origin != budget_signature:
            raise ValueError("Başlangıç bütçesi açılmış hesabın geçmişini değiştiremez; yeni hesap sürümü gerekli.")
        ledger.add("account_opened", "account_opened", now.isoformat(), **budget_signature)
        local_day = now.astimezone(IST).date().isoformat()
        fund(ledger, cfg, local_day, now.isoformat())
        errors = []
        with history.connection(root, cfg["market"], database) as con:
            if cfg["market"] == "bist":
                from src import util
                from src.calendar_bist import BistCalendar
                asof = BistCalendar(util.load_config(), con).last_closed_session(now).isoformat()
            else:
                asof = (now.astimezone(IST).date() - timedelta(days=1)).isoformat()
            frame = history.load(con, cfg["market"], asof)
            data_date = str(frame.date.max())
            # Aynı veri+ayar aynı modeli kullanır; aylık/hatalı yeniden yazım gizlenmez.
            import pandas as pd
            fingerprint = digest({"data": str(pd.util.hash_pandas_object(frame, index=False).sum()), 'engine':digest(Path(learning.__file__).read_text()), 'config': cfg})
            cache = state / "model.json"
            model = json.loads(cache.read_text()) if cache.exists() else {}
            if model.get("data_fingerprint") != fingerprint:
                model, features = learning.train(frame, cfg, data_date)
                model["data_fingerprint"] = fingerprint
                atomic_json(cache, model)
                if model.get("id"):
                    atomic_json(state / "models" / (model["id"] + ".json"), model)
                    ledger.add("model_review", "model:" + model["id"], now.isoformat(), model_id=model["id"],
                               approved=model["approved"], evaluation=model["evaluation"], limitations=model["limitations"])
            else:
                features = learning.features(frame, cfg["horizon_sessions"])
            # Model dosyası yazıldıktan sonra önceki koşu düşmüş olabilir.
            # Cache varlığı, modelin olay defterine teslim edildiğini kanıtlamaz.
            if model.get('id'):
                ledger.add('model_review', 'model:' + model['id'], now.isoformat(), model_id=model['id'],
                           approved=model['approved'], evaluation=model['evaluation'], limitations=model['limitations'])
            current = features[features.in_live == 1].groupby("symbol").tail(1).copy()
            symbols = sorted(current.symbol.unique().tolist())
            # Önceden alınmış ama izleme evreninden çıkarılmış varlık da izlenmeye devam eder.
            owned = set(ledger.account()['positions']) | set(ledger.account('benchmark')['positions'])
            current = features[features.symbol.isin(set(symbols) | owned)].groupby('symbol').tail(1).copy()
            symbols = sorted(set(symbols) | owned)
            legacy = history.legacy_summary(con, cfg["market"])
            agenda = news.collect(con, cfg["market"], now, fetch_external=not offline)
            # Kurumsal işlem bilgisi yoksa risk, sayıya eklenen hayali temettüyle örtülmez.
            corporate = []
            if cfg["market"] == "bist":
                corporate = [dict(r) for r in con.execute("SELECT ticker,date,kind,value FROM corporate_actions WHERE date>=? AND date<=?", (cfg["start_date"], local_day))]
        if quotes is None:
            try:
                quotes = {} if offline else marketdata.fetch(cfg, symbols, now)
            except Exception as exc:
                quotes = {}
                errors.append("Banka fiyat kaynağı alınamadı: " + type(exc).__name__)
        # Eksik yeni kotasyon geçmiş fiyatla işlem gerçekleştiremez.
        ledger.add("quote_snapshot", "quotes:" + digest(quotes), now.isoformat(), quotes=quotes)
        action_health = {}
        if cfg['market'] == 'bist' and not offline:
            action_health = corporate_module.refresh(symbols, state, now)
            for h in action_health.values():
                corporate.extend(h.get('actions', []))
        blocked_symbols = corporate_module.reconcile(ledger, corporate, cfg, now)
        for symbol, h in action_health.items():
            if not h['ok']:
                blocked_symbols[symbol] = 'Temettü/bölünme kaynağı doğrulanamadı.'
        cfg['blocked_symbols'] = blocked_symbols
        account = ledger.account()
        outcomes.resolve(ledger, features, cfg, now)
        scorecard = outcomes.calibration(ledger, cfg)
        forecasts = {}
        if model.get("ready"):
            valid = current.dropna(subset=learning.FEATURES)
            forecasts = dict(zip(valid.symbol, learning.predict(model, valid).tolist()))
        raw_forecasts = dict(forecasts)
        forecasts = {s: f - scorecard['correction_pct'] for s, f in forecasts.items()}
        current_view = policy.value_account(account, quotes, cfg)
        learned = feedback(ledger, current_view)
        benchmark_before = policy.value_account(ledger.account('benchmark'), quotes, cfg)
        cfg['live_gate_passed'] = (learned['roundtrips'] >= cfg['learning']['min_live_roundtrips']
                                  and current_view['equity_try'] is not None and benchmark_before['equity_try'] is not None
                                  and current_view['equity_try'] > benchmark_before['equity_try'])
        # Geçmiş performans gözlemdir: kendi düzelmesini engelleyen kalıcı kilit kurma.
        cfg['risk_multiplier'] = .25 if (learned.get('drawdown_pct') or 0) <= -cfg['learning']['max_live_drawdown_pct'] else 1
        imminent = [e for e in agenda.get('upcoming',[]) if 0 <= (datetime.fromisoformat(e['date']).date()-now.astimezone(IST).date()).days <= 1]
        if imminent:
            cfg['risk_multiplier'] *= .5
        decisions = []
        # V1 LLM yorumları bağlam olarak görünür; eski varsayımsal veto V2'yi kilitlemez.
        for row in current.to_dict("records"):
            symbol = row["symbol"]
            block = marketdata.usable(quotes.get(symbol), cfg, now, cfg["holidays"], allow_wide_spread=symbol in account['positions'])
            if symbol in blocked_symbols:
                block = blocked_symbols[symbol]
            d = policy.decision(row, forecasts.get(symbol), model, cfg, quotes.get(symbol), account["positions"].get(symbol), block, now)
            if imminent:
                d['event_note'] = 'Fed kararı yaklaşıyor; yeni sanal işlem tutarı yarıya indirildi.'
            if cfg["market"] == "gold" and d["action"] == "TUT":
                last_buy = max((f["at"] for f in account["fills"] if f["symbol"] == symbol and f["side"] == "BUY"), default="")
                if last_buy[:7] < local_day[:7]:
                    topup = policy.decision(row, forecasts.get(symbol), model, cfg, quotes.get(symbol), None, block, now)
                    if topup["action"] == "AL":
                        d = {**topup, "monthly_topup": True}
            d["key"] = "decision:" + digest({"day": local_day, "data": d, "quote": quotes.get(symbol)})
            decisions.append(d)
        fills = policy.execute(ledger, cfg, decisions, quotes, now)
        outcomes.record(ledger, decisions, raw_forecasts, now)
        for d in decisions:
            ledger.add("decision", d["key"], now.isoformat(), **{k: v for k, v in d.items() if k != "key"})
        benchmark_step(ledger, cfg, quotes, symbols, now)
        strategy = policy.value_account(ledger.account(), quotes, cfg)
        benchmark = policy.value_account(ledger.account("benchmark"), quotes, cfg)
        learned = feedback(ledger, strategy)
        baseline_nav = benchmark_nav(ledger, benchmark)
        if strategy["valuation_complete"]:
            ledger.add("valuation", "valuation:" + now.isoformat(), now.isoformat(), equity_try=strategy["equity_try"],
                       contributed_try=strategy["contributed_try"], nav=learned["nav"], benchmark_try=benchmark["equity_try"], benchmark_nav=baseline_nav)
        valuations = [dict(e["data"], at=e["at"]) for e in ledger.events if e["kind"] == "valuation"]
        # Ekran son 500 GÜNÜ alır; saatlik koşular geçmişi birkaç haftaya daraltmaz.
        daily_values = {datetime.fromisoformat(v['at']).astimezone(IST).date().isoformat(): v for v in valuations}
        learned["live_gate_passed"] = (learned["roundtrips"] >= cfg["learning"]["min_live_roundtrips"]
                                         and strategy.get("equity_try") is not None and benchmark.get("equity_try") is not None
                                         and strategy["equity_try"] > benchmark["equity_try"])
        learned['risk_multiplier'] = cfg['risk_multiplier']
        learned['scorecard'] = scorecard
        if cfg["market"] == "gold" and quotes.get("GRAM"):
            cost = quotes["GRAM"]["ask"] * (1 + cfg["gold_buy_tax_rate"])
            for view in (strategy, benchmark):
                held = sum(float(p["quantity"]) for p in view["positions"])
                view["gold_equivalent_grams"] = held + view["cash_try"] / cost
        snapshot = {"schema_version": 2, "market": cfg["market"], "generated_at": now.isoformat(),
                    "analysis_date": data_date, "mode": "paper", "strategy": strategy, "benchmark": benchmark,
                    "decisions": decisions, "quotes": quotes, "news": agenda, "learning": {k: model.get(k) for k in ("id", "asof", "ready", "status", "approved", "training_rows", "training_dates", "evaluation", "limitations", "features")},
                    "feedback": learned, "history": list(daily_values.values())[-500:], "legacy": legacy,
                    "health": {"errors": errors, "quote_coverage": len(quotes), "expected_quotes": len(symbols), 'corporate_sources': action_health,
                               "news_sources_ok": sum(s["ok"] for s in agenda["sources"]), "ledger_hash": ledger.root_hash},
                    "budget": budget_signature, 'cost_notes': cfg.get('cost_notes', []), "costs": {k: cfg[k] for k in ("commission_rate", "commission_min_try", "commission_bsmv_rate", "exchange_fee_rate", "gold_buy_tax_rate", "slippage_bps")}}
        ledger.save()
        atomic_json(state / "latest.json", snapshot)
        if notify and not offline:
            from .notifications import publish
            publish(root, cfg, snapshot, ledger, now)
        return snapshot
