"""Karar ve portföy muhasebesi saftır; LLM fiyat/işlem büyüklüğü üretemez."""
from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR
from zoneinfo import ZoneInfo

from .ledger import cents


def fee(cfg, notional, side):
    if notional <= 0:
        return 0
    if cfg["market"] == "gold":
        return cents(notional * cfg["gold_buy_tax_rate"]) if side == "BUY" else 0
    commission = max(notional * cfg["commission_rate"], min(cfg["commission_min_try"], notional * 0.01))
    return cents(commission * (1 + cfg["commission_bsmv_rate"]) + notional * cfg["exchange_fee_rate"])


def execution_price(quote, cfg, side):
    px = quote["ask"] if side == "BUY" else quote["bid"]
    slip = cfg["slippage_bps"] / 10000 if cfg["market"] == "bist" else 0
    return px * (1 + slip if side == "BUY" else 1 - slip)


def quantity_for(budget_cents, price, cfg):
    step = Decimal("1") if cfg["market"] == "bist" else Decimal("0.01")
    # Önce komisyon payı ayrılır; son kontrol kuruşa yuvarlanan GERÇEK masrafla.
    upper = Decimal(str(budget_cents / 100 / price))
    qty = (upper / step).to_integral_value(rounding=ROUND_FLOOR) * step
    while qty > 0:
        total = float(qty) * price
        if cents(total) + fee(cfg, total, "BUY") <= budget_cents:
            return qty
        qty -= step
    return Decimal(0)


def value_account(account, quotes, cfg):
    positions = []
    value = account["cash_cents"] + account.get('receivable_cents', 0)
    complete = True
    for symbol, p in account["positions"].items():
        q = quotes.get(symbol)
        mark = execution_price(q, cfg, "SELL") if q else None
        net = cents(float(p["quantity"]) * mark) - fee(cfg, float(p["quantity"]) * mark, "SELL") if mark else None
        if net is None:
            complete = False
        else:
            value += net
        positions.append({"symbol": symbol, "quantity": str(p["quantity"]),
                          "cost_try": p["cost_cents"] / 100, "average_cost": p["cost_cents"] / 100 / float(p["quantity"]),
                          "mark": mark, "value_try": net / 100 if net is not None else None,
                          "pnl_try": (net - p["cost_cents"]) / 100 if net is not None else None,
                          **{k: p.get(k) for k in ("stop", "target", "deadline", "opened_at")}})
    return {"cash_try": account["cash_cents"] / 100, "contributed_try": account["contributed_cents"] / 100,
            'receivable_try': account.get('receivable_cents', 0) / 100,
            "equity_try": value / 100 if complete else None,
            "pnl_try": (value - account["contributed_cents"]) / 100 if complete else None,
            "realized_try": account["realized_cents"] / 100, "positions": positions,
            "fills": account["fills"], "valuation_complete": complete}


def decision(row, forecast, model, cfg, quote, position, blocked, now):
    symbol = row["symbol"]
    reasons = []
    action, code = "BEKLE", "no_edge"
    today = now.astimezone(ZoneInfo('Europe/Istanbul')).date()
    age = (today - date.fromisoformat(row["date"])).days
    if age > cfg["max_analysis_age_days"]:
        blocked = "Analiz verisi eski; yeni kapanış gerekli."
    if not bool(row.get("quality_ok", False)):
        blocked = "Fiyat geçmişi kalite kontrolünü geçmedi."
    buy = execution_price(quote, cfg, "BUY") if quote else None
    sell = execution_price(quote, cfg, "SELL") if quote else None
    # Kapanıştan bu yana gerçekleşen yükselişi ikinci kez gelecek kazanç sayma.
    reference = quote.get('reference_price') if quote and cfg['market'] == 'gold' else quote.get('bid') if quote else None
    remaining = ((row.get('close', reference) * (1 + forecast / 100) / reference - 1) * 100
                 if forecast is not None and reference else forecast)
    if cfg['market'] == 'gold' and quote and not quote.get('reference_price') and not position:
        blocked = blocked or 'Gün içi ons/kur referansı doğrulanamadı; yeni alım bekliyor.'
    if blocked:
        action, code = "VERİ BEKLENİYOR", "data_block"
        reasons.append(blocked)
    elif position:
        stop, target = position.get("stop"), position.get("target")
        if stop and sell <= stop:
            action, code = "SAT", "stop"
            reasons.append("Fiyat zarar sınırının altına indi.")
        elif target and sell >= target:
            action, code = "SAT", "target"
            reasons.append("Sanal pozisyon kâr alma seviyesine ulaştı.")
        elif cfg["market"] == "bist" and position.get("deadline") and today.isoformat() >= position["deadline"]:
            action, code = "SAT", "time_exit"
            reasons.append("Pozisyonun izleme süresi doldu.")
        elif remaining is not None and remaining < -cfg["min_expected_net_pct"] and row["trend50"] < 0:
            action, code = "SAT", "forecast_reversal"
            reasons.append("Model görünümü negatife döndü; fiyat kısa trendin altında.")
        else:
            action, code = "TUT", "hold"
            reasons.append("Satış sınırlarından hiçbiri tetiklenmedi.")
    elif forecast is None or not model.get("ready"):
        reasons.append("Alım için yeterli model verisi yok.")
    else:
        roundtrip = ((buy / sell - 1) * 100 + (fee(cfg, 1000, "BUY") + fee(cfg, 1000, "SELL")) / 1000)
        net = remaining - roundtrip
        if net >= cfg["min_expected_net_pct"] and row["trend50"] > 0 and row["rsi14"] < 75:
            action, code = "AL", "cost_adjusted_opportunity"
            reasons.append(f"Modelin {cfg['horizon_sessions']} seanslık beklentisi masrafı aşıyor: net %{net:.1f}.")
            reasons.append("Fiyat kısa trendin üzerinde; aşırı alım sınırında değil.")
        else:
            if net < cfg['min_expected_net_pct']:
                reasons.append(f"Masraf sonrası beklenti %{net:.1f}; alım için en az %{cfg['min_expected_net_pct']:.1f} gerekiyor.")
            if row["trend50"] <= 0:
                reasons.append("Kısa trend zayıf; yeni para kullanma.")
            if row["rsi14"] >= 75:
                reasons.append("Kısa vadeli yükseliş hızlandı; fiyatı kovalamıyorum.")
    if model.get("ready") and not model.get("approved"):
        reasons.append("Geçmiş testte üstünlük doğrulanmadı; sanal deneme tutarı sınırlı.")
    if buy:
        vol = float(row.get('volatility20') or 0)
        volatility = max(vol / 100, .005) if math.isfinite(vol) else .005
        stop_distance = max(buy * volatility * 2.5, buy * 0.02)
        stop = buy - stop_distance
        target = sell * (1 + max(remaining or 0, 0) / 100)
        size = 1000 / buy
        buy_fee = fee(cfg, 1000, "BUY") / 100 / size
        risk_net = buy - stop + buy_fee + fee(cfg, size * stop, "SELL") / 100 / size
        reward_net = target - buy - buy_fee - fee(cfg, size * target, "SELL") / 100 / size
        rr = reward_net / risk_net if risk_net > 0 else 0
        if action == "AL" and rr < cfg["min_net_reward_risk"]:
            action, code = "BEKLE", "reward_risk"
            reasons = [f"Olası kazanç riske göre düşük: 1 TL risk için {rr:.2f} TL beklenti; en az {cfg['min_net_reward_risk']:.2f} TL gerekiyor."]
    else:
        stop = target = None
    if position:
        stop, target = position.get('stop'), position.get('target')
    return {"symbol": symbol, "asof": row["date"], "action": action, "code": code,
            "reasons": reasons[:3], "forecast_pct": forecast, 'remaining_forecast_pct': remaining, "model_id": model.get("id"),
            "stop": stop, "target": target, "price": buy,
            "sector": row.get("sector"), "confidence": "sınırlı" if not model.get("approved") else "orta",
            "deadline": position.get('deadline') if position else (today + timedelta(days=30)).isoformat() if cfg["market"] == "bist" else None}


def execute(ledger, cfg, decisions, quotes, now, book="strategy"):
    at, day = now.isoformat(), now.astimezone(ZoneInfo('Europe/Istanbul')).date().isoformat()
    actions = []
    # Satıştan sonra aynı koşuda geri alım yok; karar önceki hesabın fotoğrafıdır.
    for d in sorted(decisions, key=lambda x: (x["action"] != "SAT", -(x.get("forecast_pct") or 0), x["symbol"])):
        key = f"{book}:{day}:{d['symbol']}:{d['action']}"
        if d["action"] not in {"AL", "SAT"} or key in ledger.keys:
            continue
        account = ledger.account(book)
        symbol = d["symbol"]
        if not quotes.get(symbol):
            continue
        from .marketdata import usable
        invalid = usable(quotes[symbol], cfg, now, cfg.get("holidays", ()), allow_wide_spread=d['action']=='SAT')
        if invalid:
            d.update(action="VERİ BEKLENİYOR", code="quote_block", reasons=[invalid])
            continue
        if d["action"] == "SAT":
            if symbol not in account["positions"]:
                continue
            side = "SELL"
            qty = account["positions"][symbol]["quantity"]
        else:
            side = "BUY"
            if any(f["symbol"] == symbol and f["side"] == "SELL" and f["at"][:10] == day for f in account["fills"]):
                d.update(action="BEKLE", code="same_day_exit", reasons=["Bugün satılan varlık aynı gün geri alınmaz."])
                continue
            topping_up = cfg["market"] == "gold" and d.get("monthly_topup")
            if symbol in account["positions"] and not topping_up:
                d.update(action="TUT", code="already_owned")
                continue
            if symbol not in account["positions"] and len(account["positions"]) >= cfg["max_positions"]:
                d.update(action="BEKLE", code="capacity", reasons=["Sanal portföyde yeni pozisyon yeri yok."])
                continue
            equity = value_account(account, quotes, cfg)["equity_try"]
            if equity is None:
                d.update(action="VERİ BEKLENİYOR", code="incomplete_valuation", reasons=["Eldeki varlıkların fiyatı eksik; yeni para kullanma."])
                continue
            reserve = cents(equity * cfg["minimum_cash_pct"] / 100)
            max_notional = cents(equity * cfg["max_position_pct"] / 100)
            if (d.get("confidence") == "sınırlı" or not cfg.get('live_gate_passed', False)) and book == "strategy":
                max_notional = int(max_notional * cfg["learning"]["trial_position_multiplier"])
            max_notional = int(max_notional * cfg.get('risk_multiplier', 1))
            sector_count = sum(p.get('sector') == d.get('sector') for p in account['positions'].values())
            if cfg['market'] == 'bist' and d.get('sector') and sector_count >= cfg.get('max_positions_per_sector', 2):
                d.update(action='BEKLE', code='sector_cap', reasons=['Aynı sektörde yeterince pozisyon var.'])
                continue
            if symbol in account["positions"]:
                held = float(account["positions"][symbol]["quantity"]) * execution_price(quotes[symbol], cfg, "SELL")
                max_notional = max(0, max_notional - cents(held))
            risk = (d["price"] - d["stop"]) / d["price"] if d.get("stop") else 1
            held_risk = sum(max(0, float(p['quantity']) * (execution_price(quotes[s], cfg, 'SELL') - (p.get('stop') or 0))) for s, p in account['positions'].items() if s == symbol)
            allowed_risk = cents(max(0, equity * cfg["risk_per_trade_pct"] / 100 * cfg.get('risk_multiplier', 1) - held_risk))
            max_risk = int(allowed_risk / risk)
            budget = max(0, min(account["cash_cents"] - reserve, max_notional, max_risk))
            qty = quantity_for(budget, execution_price(quotes[symbol], cfg, side), cfg)
            step = Decimal('1') if cfg['market']=='bist' else Decimal('0.01')
            price_now = execution_price(quotes[symbol], cfg, side)
            while qty > 0:
                full_risk = (cents(float(qty)*price_now) + fee(cfg,float(qty)*price_now,'BUY')
                             - cents(float(qty)*d['stop']) + fee(cfg,float(qty)*d['stop'],'SELL'))
                if full_risk <= allowed_risk:
                    break
                qty -= step
            if qty <= 0:
                d.update(action="BEKLE", code="budget", reasons=["Masraflar ve risk sınırı sonrası bütçe en küçük alıma yetmiyor."])
                continue
        price = execution_price(quotes[symbol], cfg, side)
        notional = float(qty) * price
        if side == 'BUY':
            target_value = float(qty) * d['target']
            stop_value = float(qty) * d['stop']
            cost = cents(notional) + fee(cfg, notional, 'BUY')
            reward = cents(target_value) - fee(cfg, target_value, 'SELL') - cost
            risk_amount = cost - cents(stop_value) + fee(cfg, stop_value, 'SELL')
            if risk_amount <= 0 or reward / risk_amount < cfg['min_net_reward_risk']:
                d.update(action='BEKLE', code='sized_reward_risk', reasons=['Gerçek adet ve asgari komisyonla kazanç/risk oranı yetersiz.'])
                continue
        payload = {"book": book, "symbol": symbol, "side": side, "quantity": str(qty), "price": price,
                   "notional_cents": cents(notional), "fee_cents": fee(cfg, notional, side),
                   "decision_key": d.get("key"), "reason": d["code"], "quote": quotes[symbol],
                   "stop": d.get("stop"), "target": d.get("target"), "deadline": d.get("deadline"), 'sector': d.get('sector')}
        ledger.add("fill", key, at, **payload)
        ledger.account(book)  # Defter negatif bakiyeyi/hayalet satışı diske yazmadan reddeder.
        actions.append(payload)
        d["execution"] = {"quantity": str(qty), "price": price, "fee_try": payload["fee_cents"] / 100}
    return actions
