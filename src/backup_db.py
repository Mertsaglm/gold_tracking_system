"""SQLite güvenli dump (online .backup API'si).

Çalışan DB'yi düz kopyalamak WAL yüzünden bozuk yedek üretebilir; sqlite3 backup
API'si tutarlı bir anlık görüntü alır.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import util


def safe_backup(cfg: dict) -> str:
    src = util.abspath(cfg["paths"]["db"])
    out_dir = util.abspath("data/backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    # tarih arg'siz new Date() yok; dosya adında sabit isim + git geçmişi versiyonlar
    dst = out_dir / "altin_latest.sqlite"
    con = sqlite3.connect(str(src))
    bck = sqlite3.connect(str(dst))
    with bck:
        con.backup(bck)
    bck.close()
    con.close()
    size = Path(dst).stat().st_size
    print(f"[backup_db] tutarli dump: {dst} ({size} bayt)")
    return str(dst)


if __name__ == "__main__":
    util.load_env()
    safe_backup(util.load_config())
