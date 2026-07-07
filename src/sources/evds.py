"""TCMB EVDS kaynağı (günlük). API key HTTP header'da (Nisan 2024 kuralı).

Key yoksa sessizce atlar. Keşif fonksiyonları evds_series.json'ı zenginleştirir.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from .. import util

log = logging.getLogger("evds")


def _headers() -> dict:
    key = util.env("EVDS_API_KEY")
    return {"key": key or "", "User-Agent": "altin-mvp/1.0"}


def available() -> bool:
    return bool(util.env("EVDS_API_KEY"))


def fetch_series(cfg: dict, series_code: str,
                 start: Optional[str] = None, end: Optional[str] = None) -> list[dict]:
    """Bir seriyi çeker. [{date, value}] döner. Hata → boş liste."""
    ec = cfg["sources"]["evds"]
    if not available():
        log.info("EVDS_API_KEY yok, %s atlandı", series_code)
        return []
    from datetime import date
    start = start or ec["start_date"]
    end = end or date.today().strftime("%d-%m-%Y")
    url = (f"{ec['base']}/series={series_code}&startDate={start}&endDate={end}"
           f"&type=json")
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
        r.raise_for_status()
        js = r.json()
    except Exception as e:
        log.warning("EVDS %s hata: %s", series_code, e)
        return []
    items = js.get("items", []) if isinstance(js, dict) else []
    out = []
    field = series_code.replace(".", "_")
    for it in items:
        raw = it.get(field) or it.get(series_code)
        out.append({"date": it.get("Tarih"), "value": _parse_evds_value(raw)})
    return out


def _parse_evds_value(raw) -> Optional[float]:
    """EVDS değerleri standart nokta-ondalıklı ('45.71340000'). TR parse KULLANMA."""
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


# ---------- Keşif (kurulumun parçası) ----------
# datagroups(mode=0) tüm grupları verir; adına göre filtreleyip serieList ile serileri çekeriz.
_KEYWORDS = {
    "gold_series": ["altın", "altin", "kıymetli maden", "kiymetli maden"],
    "rate_series": ["faiz", "mevduat", "fonlama", "politika"],
    "survey_series": ["beklenti", "anket", "katılımcı", "katilimci", "enflasyon bek"],
}


def discover(cfg: dict) -> dict:
    """datagroups(mode=0) -> ad filtresi -> serieList ile kod haritası çıkarır."""
    base = cfg["sources"]["evds"]["base"]
    if not available():
        log.warning("EVDS_API_KEY yok, keşif atlandı")
        return {}
    result = {"gold_series": [], "rate_series": [], "survey_series": []}
    try:
        groups = requests.get(f"{base}/datagroups/mode=0&type=json",
                              headers=_headers(), timeout=40).json()
    except Exception as e:
        log.warning("EVDS datagroups hata: %s", e)
        return result
    for g in groups if isinstance(groups, list) else []:
        name = (g.get("DATAGROUP_NAME") or "").lower()
        dgc = g.get("DATAGROUP_CODE")
        if not dgc:
            continue
        bucket = next((b for b, kws in _KEYWORDS.items() if any(k in name for k in kws)), None)
        if not bucket:
            continue
        try:
            series = requests.get(f"{base}/serieList/type=json&code={dgc}",
                                  headers=_headers(), timeout=30).json()
            for s in series if isinstance(series, list) else []:
                if s.get("SERIE_CODE"):
                    result[bucket].append({
                        "code": s.get("SERIE_CODE"),
                        "name": s.get("SERIE_NAME"),
                        "group": dgc,
                    })
        except Exception as e:
            log.warning("keşif serieList hata (%s): %s", dgc, e)
    return result
