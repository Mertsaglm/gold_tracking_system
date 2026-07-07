"""Bildirim motoru saf çekirdek testleri: eşik değerlendirme + soğuma/tavan."""
from src import notify, util

CFG = util.load_config()


def _ctx(**kw):
    base = {"all_fresh": True, "prim": 0.0, "prim_z": None, "spread": None,
            "spread_p90": None, "daily_move": None, "atr": None, "quarter_z": None}
    base.update(kw)
    return base


def test_prim_threshold_fires():
    al = notify.evaluate_thresholds(_ctx(prim=2.0), CFG)
    assert any(a["tip"] == "prim_sapma" for a in al)


def test_prim_within_band_no_fire():
    al = notify.evaluate_thresholds(_ctx(prim=0.5), CFG)
    assert not any(a["tip"] == "prim_sapma" for a in al)


def test_zscore_threshold():
    al = notify.evaluate_thresholds(_ctx(prim_z=2.5), CFG)
    assert any(a["tip"] == "prim_z" for a in al)


def test_spread_p90():
    al = notify.evaluate_thresholds(_ctx(spread=0.5, spread_p90=0.3), CFG)
    assert any(a["tip"] == "makas" for a in al)


def test_daily_move_atr():
    al = notify.evaluate_thresholds(_ctx(daily_move=100, atr=40), CFG)  # 100 > 2*40
    assert any(a["tip"] == "gunluk_hareket" for a in al)


def test_weekend_suppresses_anomaly():
    # üç bacak FRESH değil -> anomali bildirimi yok
    al = notify.evaluate_thresholds(_ctx(all_fresh=False, prim=5.0, prim_z=9.0), CFG)
    assert al == []


def test_each_alert_has_triple():
    al = notify.evaluate_thresholds(_ctx(prim=2.0), CFG)[0]
    assert al["kural"] and al["gerekce"] and al["gecersizlik"]


# ---------- soğuma / tavan ----------
def test_cooldown_blocks_repeat():
    alerts = [{"tip": "prim_sapma", "kural": "k", "deger": 2, "gerekce": "g", "gecersizlik": "x"}]
    # 1 saat önce gönderilmiş, soğuma 24s -> engellenir
    state = {"last_sent": {"prim_sapma": "2026-07-07T10:00:00+00:00"}, "daily": {}}
    to_send, _ = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 6)
    assert to_send == []


def test_cooldown_allows_after_window():
    alerts = [{"tip": "prim_sapma", "kural": "k", "deger": 2, "gerekce": "g", "gecersizlik": "x"}]
    state = {"last_sent": {"prim_sapma": "2026-07-06T10:00:00+00:00"}, "daily": {}}
    # 25 saat sonra -> geçer
    to_send, ns = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 6)
    assert len(to_send) == 1
    assert ns["last_sent"]["prim_sapma"] == "2026-07-07T11:00:00+00:00"


def test_daily_cap():
    alerts = [{"tip": f"t{i}", "kural": "k", "deger": 1, "gerekce": "g", "gecersizlik": "x"}
              for i in range(10)]
    state = {"last_sent": {}, "daily": {}}
    to_send, ns = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 3)
    assert len(to_send) == 3            # tavan
    assert ns["daily"]["2026-07-07"] == 3
