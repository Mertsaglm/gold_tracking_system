"""Süreç yöneticisi / watchdog (rehber C.1).

collector ve telegram botunu alt-süreç olarak başlatır, çökeni üstel geri çekilme
ile yeniden başlatır, logs/supervisor.log'a yazar. Windows'ta 7/24 kalıcı çalışma
için Task Scheduler tarafından oturum açılışında başlatılır.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from . import logging_setup, util

log = None  # setup'ta atanır
_singleton_sock = None  # GC'lenmesin diye modül referansı


def _acquire_singleton(port: int) -> bool:
    """Localhost porta bind ederek tek-instance kilidi. Süreç ölünce OS serbest bırakır."""
    global _singleton_sock
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        _singleton_sock = s
        return True
    except OSError:
        s.close()
        return False


@dataclass
class Managed:
    name: str
    args: list[str]
    proc: Optional[subprocess.Popen] = None
    backoff: float = 5.0
    max_backoff: float = 300.0
    started_at: float = 0.0
    restarts: int = 0
    next_start: float = 0.0        # geri çekilme sırasında beklenen zaman

    def start(self):
        self.proc = subprocess.Popen(self.args)
        self.started_at = time.time()
        log.info("başlatıldı: %s (pid=%s)", self.name, self.proc.pid)


def _backoff_next(m: Managed, now: float, stable_seconds: float = 60.0):
    """Süreç öldü: stabil çalıştıysa backoff'u sıfırla, değilse ikiye katla."""
    uptime = now - m.started_at
    if uptime >= stable_seconds:
        m.backoff = 5.0
    else:
        m.backoff = min(m.max_backoff, m.backoff * 2)
    m.restarts += 1
    m.next_start = now + m.backoff
    log.warning("%s öldü (uptime %.0fs, çıkış). %.0fs sonra yeniden (restart #%d).",
                m.name, uptime, m.backoff, m.restarts)


def run(cfg: dict) -> None:
    global log
    log = logging_setup.setup("supervisor", cfg)
    port = cfg.get("supervisor", {}).get("singleton_port", 47615)
    if not _acquire_singleton(port):
        log.warning("Başka bir supervisor zaten çalışıyor (port %d dolu). Çıkılıyor.", port)
        return
    py = sys.executable
    managed = [
        Managed("collector", [py, "-m", "src.collector"]),
        Managed("telegram_bot", [py, "-m", "src.telegram_bot"]),
    ]
    log.info("Supervisor başladı. Yönetilen: %s", [m.name for m in managed])
    for m in managed:
        m.start()

    try:
        while True:
            now = time.time()
            for m in managed:
                if m.proc is None:
                    if now >= m.next_start:
                        m.start()
                    continue
                ret = m.proc.poll()
                if ret is not None:            # süreç bitti
                    _backoff_next(m, now)
                    m.proc = None
            time.sleep(3)
    except KeyboardInterrupt:
        log.info("Supervisor kapanıyor, alt-süreçler sonlandırılıyor.")
        for m in managed:
            if m.proc and m.proc.poll() is None:
                m.proc.terminate()
        for m in managed:
            if m.proc:
                try:
                    m.proc.wait(timeout=10)
                except Exception:
                    m.proc.kill()


if __name__ == "__main__":
    util.load_env()
    run(util.load_config())
