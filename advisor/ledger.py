"""Atomik, zincir mühürlü olay defteri. TL kuruş, miktar Decimal'dır.

Bir koşunun tamamı tek os.replace ile görünür olur. Tekrarlanan olay anahtarı
ikinci işlem üretemez. Geçmiş satır değiştirilirse defter açılmaz.
"""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        f.write(canonical(value) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


@contextmanager
def locked(path: Path):
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.events = []
        self.keys = set()
        self.root_hash = "0" * 64
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                payload = {k: v for k, v in row.items() if k != "hash"}
                if row.get("previous") != self.root_hash or digest(payload) != row.get("hash"):
                    raise ValueError("Defter bütünlüğü bozuk; geçmiş değiştirilemez.")
                if row["key"] in self.keys:
                    raise ValueError("Defterde yinelenen olay anahtarı.")
                self.events.append(row)
                self.keys.add(row["key"])
                self.root_hash = row["hash"]

    def add(self, kind, key, at, **payload):
        if key in self.keys:
            return False
        row = {"kind": kind, "key": key, "at": at, "data": payload, "previous": self.root_hash}
        row["hash"] = digest(row)
        self.events.append(row)
        self.keys.add(key)
        self.root_hash = row["hash"]
        return True

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".jsonl.tmp")
        with temp.open("w", encoding="utf-8") as f:
            for event in self.events:
                f.write(canonical(event) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.path)

    def account(self, book="strategy"):
        cash = 0
        contributed = 0
        realized = 0
        receivable = 0
        positions = {}
        fills = []
        for event in self.events:
            d = event["data"]
            if d.get("book") != book:
                continue
            if event["kind"] == "contribution":
                cash += d["amount_cents"]
                contributed += d["amount_cents"]
            elif event["kind"] == "fill":
                qty = Decimal(d["quantity"])
                if qty <= 0 or d["notional_cents"] <= 0 or d["fee_cents"] < 0:
                    raise ValueError("Defterde geçersiz işlem miktarı.")
                symbol = d["symbol"]
                p = positions.setdefault(symbol, {"quantity": Decimal(0), "cost_cents": 0})
                if d["side"] == "BUY":
                    cash -= d["notional_cents"] + d["fee_cents"]
                    p["quantity"] += qty
                    p["cost_cents"] += d["notional_cents"] + d["fee_cents"]
                    p.update({k: d.get(k) for k in ("stop", "target", "deadline", "decision_key", 'sector')})
                    p["opened_at"] = event["at"]
                elif d["side"] == "SELL":
                    if qty > p["quantity"]:
                        raise ValueError("Elde olmayan varlık satılamaz.")
                    cost = int((Decimal(p["cost_cents"]) * qty / p["quantity"]).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                    cash += d["notional_cents"] - d["fee_cents"]
                    realized += d["notional_cents"] - d["fee_cents"] - cost
                    p["quantity"] -= qty
                    p["cost_cents"] -= cost
                else:
                    raise ValueError("Bilinmeyen işlem yönü.")
                if cash < 0:
                    raise ValueError("Sanal hesap bakiyesi eksiye düşemez.")
                fills.append({**d, "at": event["at"]})
            elif event["kind"] == "corporate_action":
                # Temettü nakdi net tutarla; bölünme oranı adet ve seviyeleri değiştirir.
                symbol = d["symbol"]
                if symbol in positions:
                    p = positions[symbol]
                    if d["action"] == "split":
                        ratio = Decimal(str(d["ratio"]))
                        if ratio <= 0:
                            raise ValueError("Geçersiz bölünme oranı.")
                        p["quantity"] *= ratio
                        for k in ("stop", "target"):
                            if p.get(k):
                                p[k] /= float(ratio)
                    else:
                        cash += d["net_cents"]
            elif event['kind'] == 'dividend_receivable':
                receivable += d['amount_cents']
        return {"cash_cents": cash, "contributed_cents": contributed,
                "realized_cents": realized, 'receivable_cents': receivable,
                "positions": {k: v for k, v in positions.items() if v["quantity"] > 0}, "fills": fills}


def fund(ledger, cfg, day, at):
    from datetime import date
    start = date.fromisoformat(cfg["start_date"])
    end = date.fromisoformat(day)
    if end < start:
        return
    for book in ("strategy", "benchmark"):
        ledger.add("contribution", f"{book}:initial", at, book=book, amount_cents=cents(cfg["initial_try"]), period=start.isoformat())
        year, month = start.year, start.month
        while True:
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            if (year, month) > (end.year, end.month):
                break
            period = f"{year:04d}-{month:02d}"
            ledger.add("contribution", f"{book}:monthly:{period}", at, book=book,
                       amount_cents=cents(cfg["monthly_try"]), period=period)
