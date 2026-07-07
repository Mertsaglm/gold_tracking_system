"""Piyasa durum makinesi (rehber 1.3).

Her veri bacağına durum etiketi verir. Prim sinyali yalnız üç bacak da FRESH
iken 'geçerli' (indicative=False). Aksi halde prim hesaplanır ama indicative=True.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .market_calendar import MarketCalendar

FRESH = "FRESH"
STALE = "STALE"
CLOSED_WEEKEND = "CLOSED_WEEKEND"
CLOSED_HOLIDAY = "CLOSED_HOLIDAY"
NO_DATA = "NO_DATA"

# Bacak tipleri
LEG_ONS = "ons"          # forex seansına tabi (yfinance)
LEG_KUR = "kur"          # forex seansına tabi (yfinance)
LEG_GRAM = "gram"        # Truncgil serbest piyasa, 7/24


@dataclass
class LegState:
    leg: str
    status: str
    age_seconds: Optional[float]
    signal_grade: bool     # sadece FRESH ise True


def _age(now_utc: datetime, last_utc: Optional[datetime]) -> Optional[float]:
    if last_utc is None:
        return None
    return (now_utc - last_utc).total_seconds()


def leg_status(
    leg: str,
    now_utc: datetime,
    last_utc: Optional[datetime],
    cfg: dict,
    cal: MarketCalendar,
) -> LegState:
    age = _age(now_utc, last_utc)
    stale = cfg["market"]["stale_seconds"]

    # 1) Forex bacakları: seans kapalıysa CLOSED_* (yaş önemsiz)
    if leg in (LEG_ONS, LEG_KUR):
        if cal.is_us_gold_holiday(now_utc):
            return LegState(leg, CLOSED_HOLIDAY, age, False)
        if cal.is_weekend_closed_forex(now_utc):
            return LegState(leg, CLOSED_WEEKEND, age, False)
        thr = stale["yfinance"]
    else:
        # Gram bacağı 7/24. Fiziki tatilde online kotasyon sürer ama likidite düşük.
        if cal.is_night_local(now_utc):
            thr = stale["truncgil_gece"]
        else:
            thr = stale["truncgil_gunduz"]

    if last_utc is None:
        return LegState(leg, NO_DATA, None, False)
    if age is not None and age <= thr:
        return LegState(leg, FRESH, age, True)
    return LegState(leg, STALE, age, False)


@dataclass
class PrimValidity:
    indicative: bool          # True => sinyal/bildirim üretme
    weekend: bool             # forex hafta sonu kapalı
    holiday: bool
    reason: str
    legs: dict


def prim_validity(
    now_utc: datetime,
    last_ons: Optional[datetime],
    last_kur: Optional[datetime],
    last_gram: Optional[datetime],
    cfg: dict,
    cal: MarketCalendar,
) -> PrimValidity:
    ons = leg_status(LEG_ONS, now_utc, last_ons, cfg, cal)
    kur = leg_status(LEG_KUR, now_utc, last_kur, cfg, cal)
    gram = leg_status(LEG_GRAM, now_utc, last_gram, cfg, cal)
    legs = {LEG_ONS: ons, LEG_KUR: kur, LEG_GRAM: gram}

    all_fresh = all(s.signal_grade for s in legs.values())
    weekend = ons.status == CLOSED_WEEKEND or kur.status == CLOSED_WEEKEND
    holiday = ons.status == CLOSED_HOLIDAY or kur.status == CLOSED_HOLIDAY

    if all_fresh:
        reason = "tum_bacaklar_taze"
    else:
        bad = [f"{k}:{v.status}" for k, v in legs.items() if not v.signal_grade]
        reason = "gecersiz_bacak=" + ",".join(bad)

    return PrimValidity(
        indicative=not all_fresh,
        weekend=weekend,
        holiday=holiday,
        reason=reason,
        legs=legs,
    )
