"""Piyasa takvimi: forex (ons+kur) seansı, TR/US tatilleri, gündüz/gece.

Tüm zaman hesapları UTC üzerinden; TR yerel saati sabit UTC+3.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Set

from . import util


class MarketCalendar:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.tz_off = cfg.get("timezone_offset_hours", 3)
        m = cfg["market"]
        self.forex_open_sun_h = m["forex_open_sunday_utc_hour"]
        self.forex_close_fri_h = m["forex_close_friday_utc_hour"]
        self.gece_bas = m["gece_baslangic_hour"]
        self.gece_bit = m["gece_bitis_hour"]
        hol = util.load_yaml(cfg["paths"]["holidays_file"])
        self._tr: dict[str, Set[str]] = {
            y: set(map(str, days)) for y, days in (hol.get("tr") or {}).items()
        }
        self._us: dict[str, Set[str]] = {
            y: set(map(str, days)) for y, days in (hol.get("us") or {}).items()
        }

    # ---------- Forex seansı (ons + kur) ----------
    def is_forex_open(self, now_utc: datetime) -> bool:
        """Forex açık: Pazar 22:00 UTC -> Cuma 21:00 UTC. Cumartesi tam kapalı."""
        wd = now_utc.weekday()  # Mon=0 ... Sun=6
        h = now_utc.hour
        if wd == 5:                       # Cumartesi
            return False
        if wd == 4 and h >= self.forex_close_fri_h:   # Cuma akşamı
            return False
        if wd == 6 and h < self.forex_open_sun_h:      # Pazar (açılış öncesi)
            return False
        return True

    def is_weekend_closed_forex(self, now_utc: datetime) -> bool:
        return not self.is_forex_open(now_utc)

    # ---------- Tatiller ----------
    def _local_date_str(self, now_utc: datetime) -> str:
        return util.to_local(now_utc, self.tz_off).date().isoformat()

    def is_tr_holiday(self, now_utc: datetime) -> bool:
        d = self._local_date_str(now_utc)
        return d in self._tr.get(d[:4], set())

    def is_us_gold_holiday(self, now_utc: datetime) -> bool:
        d = now_utc.date().isoformat()
        return d in self._us.get(d[:4], set())

    # ---------- Gündüz / gece (TR yerel) ----------
    def is_night_local(self, now_utc: datetime) -> bool:
        h = util.to_local(now_utc, self.tz_off).hour
        return self.gece_bas <= h < self.gece_bit

    def is_weekend_local(self, now_utc: datetime) -> bool:
        return util.to_local(now_utc, self.tz_off).weekday() >= 5
