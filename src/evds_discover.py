"""EVDS keşif script'i — kurulumun parçası.

categories -> datagroups -> serieList gezip bulunan kodları evds_series.json'a yazar.
Config'teki doğrulanmış kodları da 'confirmed' altında saklar.
"""
from __future__ import annotations

import logging

from . import util
from .sources import evds

log = logging.getLogger("evds_discover")


def main(cfg: dict) -> dict:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    out = {
        "confirmed": cfg["sources"]["evds"]["series"],
        "discovered": {},
    }
    if not evds.available():
        log.warning("EVDS_API_KEY yok — sadece config'teki doğrulanmış kodlar yazıldı.")
    else:
        out["discovered"] = evds.discover(cfg)
        log.info("keşif: %d altın, %d faiz, %d anket serisi",
                 len(out["discovered"].get("gold_series", [])),
                 len(out["discovered"].get("rate_series", [])),
                 len(out["discovered"].get("survey_series", [])))
    util.write_json(cfg["paths"]["evds_series_file"], out)
    log.info("yazıldı: %s", cfg["paths"]["evds_series_file"])
    return out


if __name__ == "__main__":
    util.load_env()
    main(util.load_config())
