"""Tüm kaynak dosyaları, üretim tabloları ve Telegram geçmişi için tekrar koşulur envanter."""
from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

from .history import legacy_summary


def audit(root, con, market, telegram=None):
    files = []
    folders = ("src", "tests", "ai", "docs", "reports", ".github", "advisor", "dashboard", "ops")
    groups = [list(root.glob('*'))] + [list((root / folder).rglob('*')) for folder in folders]
    for group in groups:
        for p in sorted(group):
            if (p.is_file() and p.suffix in {".py", ".md", ".yaml", ".yml", ".json", '.toml', '.js', '.mjs', '.css', '.html', '.sh', '.txt'}
                and not set(p.parts) & {'__pycache__', 'node_modules', '.vercel'}
                and not p.name.startswith('revizyon-denetimi')):
                text = p.read_text(encoding="utf-8")
                entry = {"file": str(p.relative_to(root)), "lines": len(text.splitlines()), "sha256": hashlib.sha256(text.encode()).hexdigest()}
                if p.suffix == ".py":
                    tree = ast.parse(text)
                    entry["functions"] = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
                    entry["broad_handlers"] = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and (n.type is None or isinstance(n.type, ast.Name) and n.type.id == "Exception")]
                if p.suffix == ".md":
                    entry["headings"] = [x for x in text.splitlines() if x.startswith("## ")][:30]
                files.append(entry)
    tables = []
    for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
        ranges = {}
        for col in ("date", "asof", "asof_date", "ts_utc", "created_utc", "resolved_date"):
            if col in cols:
                ranges[col] = list(con.execute(f'SELECT MIN("{col}"),MAX("{col}") FROM "{table}"').fetchone())
        tables.append({"table": table, "rows": con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0], "ranges": ranges})
    chat = None
    if telegram:
        source = json.loads(Path(telegram).read_text(encoding="utf-8"))
        messages = source.get("messages", [])
        def flatten(m):
            t = m.get("text", "")
            return t if isinstance(t, str) else "".join(x if isinstance(x, str) else x.get("text", "") for x in t)
        texts = [flatten(m) for m in messages]
        lengths = sorted(map(len, texts))
        chat = {"messages": len(messages), "start": messages[0].get("date") if messages else None,
                "end": messages[-1].get("date") if messages else None,
                "mean_characters": round(sum(lengths) / len(lengths)) if lengths else 0,
                "max_characters": max(lengths, default=0),
                "phrases": {x: sum(x.lower() in t.lower() for t in texts) for x in ["DURDURULDU", "KAYDI YOK", "ÖLÇÜLEMİYOR", "PRİM ÖLÇÜM TAŞIMIYOR", "Plan seçildi", "HÜKÜM"]}}
    return {"market": market, "integrity": con.execute("PRAGMA quick_check").fetchone()[0],
            "files": files, "tables": tables, "legacy": legacy_summary(con, market), "telegram": chat}
