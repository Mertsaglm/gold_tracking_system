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
        val = util.parse_tr_number(raw) if raw not in (None, "") else None
        out.append({"date": it.get("Tarih"), "value": val})
    return out


# ---------- Keşif (kurulumun parçası) ----------
def discover(cfg: dict) -> dict:
    """categories -> datagroups -> serieList gezerek kod haritası çıkarır."""
    ec = cfg["sources"]["evds"]
    base = ec["base"]
    if not available():
        log.warning("EVDS_API_KEY yok, keşif atlandı")
        return {}
    result = {"categories": [], "gold_series": [], "rate_series": [], "survey_series": []}
    try:
        cats = requests.get(f"{base}/categories/key=&type=json",
                            headers=_headers(), timeout=30).json()
        for c in cats if isinstance(cats, list) else []:
            cid = c.get("CATEGORY_ID")
            title = (c.get("TOPIC_TITLE_TR") or "").lower()
            result["categories"].append({"id": cid, "title": c.get("TOPIC_TITLE_TR")})
            bucket = None
            if "altın" in title or "altin" in title:
                bucket = "gold_series"
            elif "faiz" in title:
                bucket = "rate_series"
            elif "beklenti" in title or "anket" in title:
                bucket = "survey_series"
            if not bucket or cid is None:
                continue
            try:
                groups = requests.get(
                    f"{base}/datagroups/mode=2&code={cid}&type=json",
                    headers=_headers(), timeout=30).json()
                for g in groups if isinstance(groups, list) else []:
                    dgc = g.get("DATAGROUP_CODE")
                    if not dgc:
                        continue
                    series = requests.get(
                        f"{base}/serieList/type=json&code={dgc}",
                        headers=_headers(), timeout=30).json()
                    for s in series if isinstance(series, list) else []:
                        result[bucket].append({
                            "code": s.get("SERIE_CODE"),
                            "name": s.get("SERIE_NAME"),
                            "group": dgc,
                        })
            except Exception as e:
                log.warning("keşif alt grup hata (%s): %s", cid, e)
    except Exception as e:
        log.warning("EVDS keşif hata: %s", e)
    return result
