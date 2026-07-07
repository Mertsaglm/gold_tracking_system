"""Truncgil serbest piyasa altın/döviz kaynağı (v3 JSON).

Şema toleranslı: yapılandırılmış anahtar yoksa o sembolü atlar, çökmez.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

from .. import util

log = logging.getLogger("truncgil")


@dataclass
class TruncgilSnapshot:
    ok: bool
    update_date: Optional[str] = None
    # symbol -> (buying, selling)
    prices: dict[str, tuple[Optional[float], Optional[float]]] = field(default_factory=dict)
    error: Optional[str] = None

    def bs(self, symbol: str):
        return self.prices.get(symbol, (None, None))


def fetch(cfg: dict) -> TruncgilSnapshot:
    tc = cfg["sources"]["truncgil"]
    try:
        r = requests.get(tc["url"], timeout=tc["timeout"],
                         headers={"User-Agent": "altin-mvp/1.0"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # ağ / json hatası → çökme yok
        log.warning("truncgil fetch hata: %s", e)
        return TruncgilSnapshot(ok=False, error=str(e))

    keys = tc["keys"]
    prices: dict[str, tuple] = {}
    for logical, jkey in keys.items():
        node = data.get(jkey)
        if not isinstance(node, dict):
            log.warning("truncgil anahtar yok: %s (%s)", logical, jkey)
            continue
        buying = util.parse_tr_number(node.get("Buying"))
        selling = util.parse_tr_number(node.get("Selling"))
        prices[logical] = (buying, selling)

    return TruncgilSnapshot(
        ok=bool(prices),
        update_date=data.get(tc.get("update_date_key", "Update_Date")),
        prices=prices,
    )
