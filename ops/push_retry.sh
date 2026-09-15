#!/usr/bin/env bash
# Koşu ancak uzaktaki arşive yazıldığında teslim edilmiş sayılır.
set -euo pipefail
for attempt in 1 2 3 4 5; do
  if git pull --rebase origin main && git push; then
    exit 0
  fi
  echo "Arşiv gönderimi başarısız: deneme $attempt/5" >&2
  if [ "$attempt" -lt 5 ]; then sleep "$((attempt * 5))"; fi
done
echo 'Arşiv uzak depoya kaydedilemedi.' >&2
exit 1
