#!/usr/bin/env zsh
# Mac uyanıksa V2'yi seans içinde çalıştırır; GitHub Actions yedek kalır.
set -euo pipefail

ROOT=${0:A:h:h}
cd "$ROOT"
PYTHON="$ROOT/.advisor-runtime/bin/python"
LOCK_DIR="/tmp/mertsaglm-advisor-v2-gold.lock"

log() { print -r -- "$(date -u +%FT%TZ) [gold-v2] $*"; }
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log 'Önceki yerel V2 koşusu hâlâ sürüyor; bu tetikleme atlandı.'
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

if [[ ! -x "$PYTHON" ]]; then
  log 'İzole Python 3.12 çalışma ortamı yok; koşu güvenli biçimde durduruldu.'
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  log 'Çalışma dizininde commitlenmemiş değişiklik var; kullanıcı çalışmasını ezmemek için duruldu.'
  exit 1
fi
if ! git pull --ff-only origin main; then
  log 'Uzak arşiv güvenli biçimde alınamadı; çevrim başlatılmadı.'
  exit 1
fi
if ! "$PYTHON" - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
from advisor.calendar import load, session_block
from advisor.service import configuration

root = Path.cwd()
cfg = configuration(root)
cfg['calendar'] = load(root)
raise SystemExit(0 if session_block(datetime.now(timezone.utc), cfg) is None else 1)
PY
then
  log 'Seans dışında veya tatildeyiz; V2 çevrimi gerekmiyor.'
  exit 0
fi

set -a
source "$ROOT/.env"
set +a
export ADVISOR_V2=1

set +e
"$PYTHON" -m advisor cycle
CYCLE_STATUS=$?
set -e

git add data/advisor/
if ! git diff --cached --quiet; then
  git commit -m "advisor: yerel V2 çevrimi $(date -u +%Y-%m-%dT%H:%MZ)"
  "$ROOT/ops/push_retry.sh"
fi
if (( CYCLE_STATUS != 0 )); then
  log "V2 çevrimi hata kodu $CYCLE_STATUS ile bitti; hata arşivi teslim edildi."
  exit "$CYCLE_STATUS"
fi

"$PYTHON" -m advisor notify
git add data/advisor/
if ! git diff --cached --quiet; then
  git commit -m 'advisor: yerel V2 bildirim makbuzu'
  "$ROOT/ops/push_retry.sh"
fi
log 'V2 çevrimi ve teslim makbuzu tamamlandı.'
