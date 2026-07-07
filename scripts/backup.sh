#!/usr/bin/env bash
# Günlük SQLite tutarlı yedek + private GitHub reposuna push.
# Arşiv tek kopya olmamalı: bu script commit + push eder.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="data/altin.sqlite"
BACKUP_DIR="data/backups"
STAMP="$(date -u +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Tutarlı kopya (WAL dahil) — sqlite3 .backup online-safe
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB" ".backup '$BACKUP_DIR/altin_$STAMP.sqlite'"
else
  cp "$DB" "$BACKUP_DIR/altin_$STAMP.sqlite"
fi

# Son 14 yedeği tut
ls -1t "$BACKUP_DIR"/altin_*.sqlite 2>/dev/null | tail -n +15 | xargs -r rm -f

# Mutabakat job'ını da tetikle (hafta sonu -> pazartesi)
.venv/bin/python -m src.reconcile || true

git add -A
if ! git diff --cached --quiet; then
  git commit -m "backup: veri $STAMP" >/dev/null
  git push origin main
  echo "[backup] push tamam: $STAMP"
else
  echo "[backup] değişiklik yok"
fi
