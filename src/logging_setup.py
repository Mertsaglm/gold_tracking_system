"""Merkezi loglama: dönen dosya logları (RotatingFileHandler) + konsol."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import util

_configured: set[str] = set()


def setup(name: str, cfg: dict | None = None,
          max_bytes: int = 5 * 1024 * 1024, backups: int = 5) -> logging.Logger:
    """logs/<name>.log dosyasına dönen log + konsol. İkinci çağrıda tekrar eklemez."""
    logs_dir = util.abspath("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    key_file = f"file:{name}"
    if key_file not in _configured:
        fh = RotatingFileHandler(logs_dir / f"{name}.log", maxBytes=max_bytes,
                                 backupCount=backups, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        _configured.add(key_file)
    if "console" not in _configured:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        root.addHandler(ch)
        _configured.add("console")
    return logging.getLogger(name)
