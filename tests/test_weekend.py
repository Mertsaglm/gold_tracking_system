"""Bölüm 3 — İlk hafta sonu (11-13 Temmuz 2026) kuru-koşu testleri."""
from datetime import datetime, timezone, timedelta

from src import db, notify, util
from src.market_calendar import MarketCalendar
from src.report import weekend_section

CFG = util.load_config()
CAL = MarketCalendar(CFG)


def _utc(y, mo, d, h=12):
    return datetime(y, mo, d, h, 0, tzinfo=timezone.utc)


# (a) Cumartesi/Pazar forex kapalı → import weekend=1 yazacak
def test_first_weekend_forex_closed():
    assert CAL.is_weekend_closed_forex(_utc(2026, 7, 11))       # Cumartesi
    assert CAL.is_weekend_closed_forex(_utc(2026, 7, 12, 12))   # Pazar öğlen
    assert not CAL.is_weekend_closed_forex(_utc(2026, 7, 13, 12))  # Pazartesi açık


# (a) Cumartesi zamanında anomali bildirimi bastırılır
def test_saturday_anomaly_suppressed():
    ctx = {"all_fresh": False, "prim": 5.0, "prim_z": 9.0,
           "spread": None, "spread_p90": None, "daily_move": None, "atr": None,
           "quarter_z": None}
    assert notify.evaluate_thresholds(ctx, CFG) == []


# (c) Pazartesi beklentisi mesajı günde en fazla 1
def test_weekend_expectation_max_one_per_day():
    alert = [{"tip": "weekend_expectation", "kural": "k", "deger": 1,
              "gerekce": "g", "gecersizlik": "x"}]
    # ilk gönderim
    to_send, state = notify.apply_cooldown(alert, {"last_sent": {}, "daily": {}},
                                           "2026-07-11T08:00:00+00:00", 24, 1)
    assert len(to_send) == 1
    # aynı gün ikinci deneme -> soğuma engeller
    to_send2, _ = notify.apply_cooldown(alert, state,
                                        "2026-07-11T20:00:00+00:00", 24, 1)
    assert to_send2 == []


# (b) Rapor hafta sonu bölümü: veri yoksa SESSİZ
def test_weekend_section_silent_when_empty(tmp_path):
    cfg = {"paths": {"db": str(tmp_path / "t.sqlite"), "db_dump": str(tmp_path / "t.sql")},
           "timezone_offset_hours": 3}
    con = db.connect(cfg)
    assert weekend_section(con, cfg) == []       # hafta içi yanlışlıkla görünmez
    con.close()


# (b) Rapor hafta sonu bölümü: veri varsa görünür
def test_weekend_section_shows_with_data(tmp_path):
    cfg = {"paths": {"db": str(tmp_path / "t.sqlite"), "db_dump": str(tmp_path / "t.sql")},
           "timezone_offset_hours": 3}
    con = db.connect(cfg)
    ts = util.iso(util.utcnow())
    con.execute("INSERT INTO weekend_expectation(ts_utc,weekend_gram,frozen_theoretical,"
                "expectation_pct) VALUES(?,6200,6250,-0.8)", (ts,))
    con.execute("INSERT INTO prim_history(ts_utc,prim_pct,indicative,weekend) "
                "VALUES(?,-0.5,0,0)", (ts,))
    con.commit()
    out = weekend_section(con, cfg)
    con.close()
    assert out and any("Hafta Sonu Beklentisi" in line for line in out)
