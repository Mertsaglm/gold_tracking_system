"""Sabit özellikli ridge; zaman sıralı, sonuç vadesiyle ayrılan walk-forward.

Ölçek yalnız eğitimde öğrenilir. Bir etiket test gününde henüz sonuçlanmadıysa
eğitime giremez. Aynı gün hisseler tek piyasa gözlemi olarak değerlendirilir.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from .ledger import digest

FEATURES = ["momentum20", "momentum60", "momentum120", "trend50", "trend200", "volatility20", "drawdown60", "rsi14"]


def features(frame, horizon):
    parts = []
    for _, group in frame.groupby("symbol", sort=True):
        g = group.copy()
        c = g["total_close"].where(g["total_close"] > 0)
        ret = c.pct_change(fill_method=None)
        for n in (20, 60, 120):
            g[f"momentum{n}"] = c.pct_change(n, fill_method=None) * 100
        for n in (50, 200):
            g[f"trend{n}"] = (c / c.rolling(n).mean() - 1) * 100
        g["volatility20"] = ret.rolling(20).std() * 100
        g["drawdown60"] = (c / c.rolling(60).max() - 1) * 100
        gain = c.diff().clip(lower=0).rolling(14).mean()
        loss = -c.diff().clip(upper=0).rolling(14).mean()
        g["rsi14"] = (100 * gain / (gain + loss)).fillna(50)
        g["forward_pct"] = (c.shift(-horizon) / c - 1) * 100
        g["label_end"] = g["date"].shift(-horizon)
        tr = pd.concat([g.high - g.low, (g.high - g.close.shift()).abs(), (g.low - g.close.shift()).abs()], axis=1).max(axis=1)
        g["atr"] = tr.rolling(14).mean()
        # Gram tarihi ons×kur sentetik kapanıştır; ATR diye gerçek OHLC uydurulmaz.
        g["daily_jump_pct"] = ret.abs() * 100
        g["quality_ok"] = (g.close > 0) & (g.total_close > 0) & (g.volume > 0) & (g.high >= g.low)
        g["quality_ok"] &= ret.abs().rolling(20).max().fillna(1) < 0.3
        parts.append(g)
    return pd.concat(parts, ignore_index=True).replace([np.inf, -np.inf], np.nan)


def fit(rows, penalty):
    x = rows[FEATURES].to_numpy(float)
    y = rows.forward_pct.to_numpy(float)
    mu, sd = x.mean(axis=0), x.std(axis=0)
    sd[sd < 1e-8] = 1
    z = np.clip((x - mu) / sd, -5, 5)
    ym = y.mean()
    weights = np.linalg.solve(z.T @ z + np.eye(len(FEATURES)) * penalty, z.T @ (y - ym))
    return {"mean": mu.tolist(), "scale": sd.tolist(), "weights": weights.tolist(), "intercept": float(ym)}


def predict(model, rows):
    x = rows[FEATURES].to_numpy(float)
    return np.clip((x - np.array(model["mean"])) / np.array(model["scale"]), -5, 5) @ np.array(model["weights"]) + model["intercept"]


def evaluate_periods(oos, horizon, market, cost_pct, min_net=1):
    if oos.empty:
        return {"periods": 0, "mean_excess_pct": None, "lower_95_pct": None, "series": []}
    # Aynı 20 günlük fiyat hareketini her gün yeni başarı saymamak için ayrık pencereler.
    dates = sorted(oos.date.unique())
    observations = []
    next_date = ""
    for day in dates:
        if day < next_date:
            continue
        g = oos[oos.date == day]
        end = str(g.label_end.max())
        if not end or end == "nan":
            continue
        next_date = end
        if market == "bist":
            ranked = g.sort_values(["forecast", "symbol"], ascending=[False, True])
            chosen = ranked.head(max(1, math.ceil(len(g) * 0.2)))
            selected = chosen[chosen.forecast > cost_pct + min_net]
            strategy = float(selected.forward_pct.sum() / len(chosen) - cost_pct * len(selected) / len(chosen))
            baseline = float(g.forward_pct.mean() - cost_pct)
        else:
            r = g.iloc[0]
            strategy = float(r.forward_pct - cost_pct) if r.forecast > cost_pct + min_net else 0.0
            baseline = float(r.forward_pct - cost_pct)
        observations.append({"date": str(day), "end": end, "strategy_pct": strategy,
                             "baseline_pct": baseline, "excess_pct": strategy - baseline})
    values = [r["excess_pct"] for r in observations]
    n = len(values)
    mean = float(np.mean(values)) if n else None
    se = float(np.std(values, ddof=1) / np.sqrt(n)) if n > 1 else None
    return {"periods": n, "mean_excess_pct": mean,
            "lower_95_pct": mean - 1.96 * se if se is not None else None,
            "upper_95_pct": mean + 1.96 * se if se is not None else None, "series": observations}


def train(frame, cfg, asof):
    f = features(frame[frame.date <= asof], cfg["horizon_sessions"])
    valid = f.dropna(subset=FEATURES + ["forward_pct", "label_end"])
    valid = valid[(valid.label_end <= asof) & valid.quality_ok]
    dates = sorted(valid.date.unique())
    policy = cfg["learning"]
    minimum = policy["min_training_dates"]
    if len(dates) < minimum:
        return {"ready": False, "reason": "Model için yeterli geçmiş yok.", "training_dates": len(dates)}, f
    outputs = []
    folds = []
    for i in range(minimum, len(dates), policy["test_block_sessions"]):
        begin = dates[i]
        end = dates[min(i + policy["test_block_sessions"] - 1, len(dates) - 1)]
        training = valid[valid.label_end < begin]
        testing = valid[(valid.date >= begin) & (valid.date <= end)].copy()
        if len(training) < 100 or testing.empty:
            continue
        m = fit(training, policy["ridge_penalty"])
        testing["forecast"] = predict(m, testing)
        testing["mean_forecast"] = m["intercept"]
        outputs.append(testing)
        folds.append({"train_label_end": str(training.label_end.max()), "test_start": str(begin), "test_end": str(end)})
    oos = pd.concat(outputs) if outputs else pd.DataFrame()
    cost = ((cfg["commission_rate"] * (1 + cfg["commission_bsmv_rate"]) + cfg["exchange_fee_rate"]) * 200 + cfg["slippage_bps"] / 50) if cfg["market"] == "bist" else cfg["max_spread_pct"] + cfg["gold_buy_tax_rate"] * 100
    evaluation = evaluate_periods(oos, cfg["horizon_sessions"], cfg["market"], cost, cfg['min_expected_net_pct'])
    evaluation['method'] = 'Zaman sıralı tahmin taraması; tam portföy/stop simülasyonu değildir.'
    evaluation['cost_stress'] = [dict(cost_pct=cost * factor, **{
        k: v for k, v in evaluate_periods(oos, cfg['horizon_sessions'], cfg['market'], cost * factor, cfg['min_expected_net_pct']).items() if k != 'series'
    }) for factor in (1, 1.5, 2)]
    if not oos.empty:
        evaluation["mae_pct"] = float((oos.forecast - oos.forward_pct).abs().mean())
        evaluation["baseline_mae_pct"] = float((oos.mean_forecast - oos.forward_pct).abs().mean())
    promoted = (evaluation["periods"] >= policy["min_validation_periods"]
                and evaluation.get("lower_95_pct") is not None and evaluation["lower_95_pct"] > 0
                and evaluation.get("mae_pct", math.inf) < evaluation.get("baseline_mae_pct", 0))
    model = fit(valid, policy["ridge_penalty"])
    model.update(ready=True, asof=asof, training_rows=len(valid), training_dates=len(dates),
                 label_end=str(valid.label_end.max()), features=FEATURES,
                 evaluation=evaluation, folds=folds, approved=promoted,
                 status="doğrulama geçti" if promoted else "sınırlı sanal deneme",
                 cost_assumption_pct=cost,
                 limitations=["Tarihsel banka kotasyonları yok; maliyet duyarlılığı kullanıldı.",
                              "Geçmiş fiyatlar sonradan düzeltilmiş olabilir; o gün bilinen veri arşivi değildir.",
                              "Sabit güncel hisse evreni geçmişte kapanan şirketleri içermeyebilir."] if cfg["market"] == "bist" else
                              ["Geçmiş gram fiyatı vadeli ons×kur göstergesidir; İş Bankası işlem fiyatı değildir.",
                               "Tarihsel banka makası yok; sabit maliyetle stres testi yapıldı."])
    model["id"] = digest({k: model[k] for k in ("asof", "weights", "mean", "scale", "intercept", "training_rows", 'evaluation')})[:16]
    return model, f
