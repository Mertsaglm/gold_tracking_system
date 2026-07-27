#!/usr/bin/env bash
# SQLite'ın TUTARLI (WAL-güvenli) anlık görüntüsünü alır. Başka HİÇBİR ŞEY yapmaz.
#
# NEDEN BU KADAR DAR — L-007: bu dosyanın eski bir sürümü yedek almanın yanında
# sessizce `git commit && git push` yapıyordu ve ürettiği ~2.9 MB'lık binary
# dosyalar gitignore'da değildi. Ders şuydu: "Bir script'in adı ne yaptığını
# söylemez." Bu yüzden burada dışa dönük tek bir işlem yok:
#   - git yok (commit/push/add)
#   - ağ yok
#   - silme yok (üzerine yazar; eski anlık görüntü tek dosyadır)
# Çıktı `data/backups/` altına gider ve o dizin .gitignore'da — binary yedek
# repoya ASLA girmez (Faz 5'te çözülen sorunun ta kendisi).
#
# Bu script yalnız ERTELENMİŞ Oracle Cloud senaryosunda (deploy/altin-backup.timer)
# çalışır; GitHub Actions üretiminde kullanılmaz — orada kalıcılık
# `data/altin.sql` dump'ıyla sağlanır (bkz. src/dbdump.py).
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KOK"

if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    PY="$(command -v python3)"
fi

exec "$PY" -m src.backup_db
