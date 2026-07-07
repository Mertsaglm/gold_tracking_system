"""Ortak yardımcılar: TR sayı ayrıştırma, zaman, config/env yükleme."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent


# ---------- Zaman ----------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def tz_local(offset_hours: int = 3) -> timezone:
    return timezone(timedelta(hours=offset_hours))


def to_local(dt: datetime, offset_hours: int = 3) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz_local(offset_hours))


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


# ---------- TR sayı ayrıştırma ----------
def parse_tr_number(s: Any) -> Optional[float]:
    """'6.247,17' -> 6247.17 ; '46,8366' -> 46.8366 ; '%-0,34' -> -0.34."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace("%", "").replace(" ", "").replace(" ", "")
    if t in ("", "-", "N/A", "null", "None"):
        return None
    # nokta = binlik ayraç, virgül = ondalık
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# ---------- Config / env ----------
def load_config(path: str | Path = ROOT / "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env(path: str | Path = ROOT / ".env") -> None:
    """Basit .env yükleyici (harici bağımlılık yok) + SSL cacert ASCII-path düzeltmesi."""
    _ensure_ascii_cert()
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _ensure_ascii_cert() -> None:
    """Proje yolu non-ASCII ise (ör. 'altın') curl_cffi cacert'i açamaz.
    certifi cacert'ini ASCII temp yola kopyalayıp env değişkenlerini ayarlar."""
    try:
        import certifi
        src = certifi.where()
        if src.isascii():
            return  # sorun yok
        import shutil
        import tempfile
        dst = Path(tempfile.gettempdir()) / "altin_cacert.pem"
        if not str(dst).isascii():
            return  # temp de non-ASCII ise yapacak bir şey yok
        if not dst.exists():
            shutil.copy(src, dst)
        for var in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
            os.environ.setdefault(var, str(dst))
    except Exception:
        pass  # cert düzeltmesi başarısızsa sessizce devam


def env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def abspath(rel: str | Path) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p


def write_json(path: str | Path, data: Any) -> None:
    with open(abspath(path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: str | Path, default: Any = None) -> Any:
    p = abspath(path)
    if not p.exists():
        return default
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)
