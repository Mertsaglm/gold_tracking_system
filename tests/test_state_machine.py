"""Durum makinesi + takvim testleri."""
from datetime import datetime, timedelta, timezone

import pytest

from src import util
from src.market_calendar import MarketCalendar
from src import state_machine as sm

CFG = util.load_config()
CAL = MarketCalendar(CFG)


def _utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


# ---------- Forex seansı ----------
def test_forex_open_weekday():
    # Çarşamba öğlen UTC -> açık
    assert CAL.is_forex_open(_utc(2026, 7, 8, 12))


def test_forex_closed_saturday():
    assert not CAL.is_forex_open(_utc(2026, 7, 11, 12))  # Cumartesi


def test_forex_closed_friday_night():
    assert not CAL.is_forex_open(_utc(2026, 7, 10, 22))  # Cuma 22:00 UTC


def test_forex_open_sunday_evening():
    assert CAL.is_forex_open(_utc(2026, 7, 12, 23))       # Pazar 23:00 UTC -> açık
    assert not CAL.is_forex_open(_utc(2026, 7, 12, 20))   # Pazar 20:00 UTC -> kapalı


# ---------- Bacak durumları ----------
def test_leg_fresh():
    now = _utc(2026, 7, 8, 12)
    last = now - timedelta(seconds=30)
    st = sm.leg_status(sm.LEG_GRAM, now, last, CFG, CAL)
    assert st.status == sm.FRESH and st.signal_grade


def test_leg_stale_gram():
    now = _utc(2026, 7, 8, 12)          # gündüz
    last = now - timedelta(seconds=1000)  # gündüz eşiği 300s
    st = sm.leg_status(sm.LEG_GRAM, now, last, CFG, CAL)
    assert st.status == sm.STALE and not st.signal_grade


def test_leg_ons_weekend_closed():
    now = _utc(2026, 7, 11, 12)          # Cumartesi
    last = now - timedelta(seconds=30)
    st = sm.leg_status(sm.LEG_ONS, now, last, CFG, CAL)
    assert st.status == sm.CLOSED_WEEKEND and not st.signal_grade


def test_leg_no_data():
    now = _utc(2026, 7, 8, 12)
    st = sm.leg_status(sm.LEG_GRAM, now, None, CFG, CAL)
    assert st.status == sm.NO_DATA


# ---------- Prim geçerliliği ----------
def test_prim_valid_weekday_all_fresh():
    now = _utc(2026, 7, 8, 12)
    last = now - timedelta(seconds=30)
    v = sm.prim_validity(now, last, last, last, CFG, CAL)
    assert not v.indicative and not v.weekend


def test_prim_indicative_on_weekend():
    now = _utc(2026, 7, 11, 12)          # Cumartesi
    last_forex = now - timedelta(hours=15)   # ons/kur cuma kapanışı
    last_gram = now - timedelta(seconds=30)  # gram taze
    v = sm.prim_validity(now, last_forex, last_forex, last_gram, CFG, CAL)
    assert v.indicative and v.weekend


def test_prim_indicative_when_gram_stale():
    now = _utc(2026, 7, 8, 12)
    fresh = now - timedelta(seconds=30)
    stale_gram = now - timedelta(seconds=1000)
    v = sm.prim_validity(now, fresh, fresh, stale_gram, CFG, CAL)
    assert v.indicative and not v.weekend


# ---------- Tatil ----------
def test_tr_holiday_detection():
    # 2026-10-29 Cumhuriyet Bayramı, TR yerel gün
    now = _utc(2026, 10, 29, 9)  # TR 12:00
    assert CAL.is_tr_holiday(now)


def test_night_detection():
    # TR 03:00 -> UTC 00:00
    assert CAL.is_night_local(_utc(2026, 7, 8, 0))
    # TR 12:00 -> UTC 09:00
    assert not CAL.is_night_local(_utc(2026, 7, 8, 9))
