#!/bin/bash
# Usta şablonunu yeni bir projeye kopyalar.
# Kullanım: ./yeni-proje.sh /yol/YeniProje
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Kullanım: ./yeni-proje.sh /yol/YeniProje"
  exit 1
fi

KAYNAK="$(cd "$(dirname "$0")" && pwd)"
HEDEF="$1"

if [ -e "$HEDEF" ] && [ -n "$(ls -A "$HEDEF" 2>/dev/null)" ]; then
  echo "HATA: '$HEDEF' zaten var ve boş değil. Üzerine yazmamak için duruyorum."
  exit 1
fi

mkdir -p "$HEDEF/ai/archive" "$HEDEF/.github"

# Kanonik dosya + IDE köprüleri DAİMA proje köküne gider:
# hiçbir IDE alt klasördeki kural dosyasını otomatik okumaz (bkz. ai/DECISIONS.md).
cp "$KAYNAK/AGENTS.md"  "$HEDEF/"
cp "$KAYNAK/CLAUDE.md"  "$HEDEF/"
cp "$KAYNAK/GEMINI.md"  "$HEDEF/"
cp "$KAYNAK/.github/copilot-instructions.md" "$HEDEF/.github/"
# Kiro köprüsü bilinçli olarak yok (az kullanılıyor). Gerekirse
# .kiro/steering/usta.md ile AGENTS.md'ye yönlendiren 3 satır yeter.
cp "$KAYNAK/ai/PROFILE.md"  "$HEDEF/ai/"   # projeler arası ortak profil
cp "$KAYNAK/ai/LESSONS.md"  "$HEDEF/ai/"   # dersler de seninle taşınsın
cp "$KAYNAK/ai/archive/README.md" "$HEDEF/ai/archive/"

# PROJECT.md KOPYALANMAZ: kaynaktaki dosya altın projesinin kimliğiyle dolu;
# kopyalansa yeni proje yanlış bir kimliği miras alırdı. Boş şablon yazılır,
# Usta /tanis ile doldurur.
cat > "$HEDEF/ai/PROJECT.md" <<'EOF'
# PROJECT.md — Projenin Kimliği

> Bir kez yazılır, nadiren değişir. BOŞ ise Usta `/baslat` veya `/tanis` ile
> keşif protokolünü çalıştırıp burayı KENDİSİ doldurur (AGENTS.md bölüm 3).

## Proje Adı
_(örn. TaskFlow, VN-100 Arayüzü, BIST30 Takip)_

## Tek Cümlelik Amaç
_Bu proje ne işe yarıyor? Kime/neye hizmet ediyor?_

## Kapsam (Ne VAR)
- _v1'de mutlaka olacaklar_

## Kapsam Dışı (Ne YOK)
- _Bilerek yapmadıklarımız — scope creep'e karşı kalkan_

## Kısıtlar
- **Bütçe:** _(ücretsiz mi kalmalı? aylık limit?)_
- **Zaman:** _(hedef tarih var mı?)_
- **Ortam:** _(ağ kısıtları, donanım, işletim sistemi...)_
- **Diğer:** _(veri gizliliği, offline çalışma zorunluluğu vb.)_

## Teknoloji Yığını (kararlaştırıldıkça doldur)
| Katman | Seçim | Karar kaydı |
|---|---|---|
| _örn. Frontend_ | _?_ | _DECISIONS.md #001_ |

## Başarı Kriteri
_"Bu proje başarılı oldu" diyebilmemiz için ne olması lazım?_
EOF

BUGUN="$(date +%Y-%m-%d)"

# STATE.md sıfırdan başlar
cat > "$HEDEF/ai/STATE.md" <<EOF
# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi \`ai/archive/STATE-YYYY-MM.md\`'ye taşı.

**Son güncelleme:** $BUGUN
**Aktif milestone:** Başlangıç

## ✅ Tamamlananlar
- $BUGUN — Proje şablondan oluşturuldu

## 🔨 Devam Edenler
- (yok)

## 🧱 Bloklar / Bekleyenler
- (yok)

## 🎯 Sıradaki 3 İş
1. /baslat yaz — Usta proje keşfini yapsın: sorular sorup ai/PROJECT.md'yi kendisi doldursun — DoD: PROJECT.md dolu ve onaylı
2. /plan ile ilk milestone'u çıkar — DoD: 1-2 saatlik görevler + DoD'ler hazır
3. En riskli varsayımı doğrulayan ilk görevi yap — DoD: "bu iş çalışır" kanıtlandı

## 📦 Backlog (şimdi değil, unutma da)
- (boş)
EOF

# DECISIONS.md boş başlar (şablonla birlikte)
cat > "$HEDEF/ai/DECISIONS.md" <<'EOF'
# DECISIONS.md — Karar Günlüğü (ADR)

> Yalnızca ÖNEMLİ kararlar: mimari, araç, yaklaşım seçimleri.
> Her karar "neden"i ve "tekrar gözden geçirme koşulu" ile kaydedilir.
> En yeni karar en üste.

---

<!-- Yeni karar şablonu:

## #NNN — YYYY-MM-DD — Kısa başlık

**Bağlam:** Hangi sorun/ihtiyaç bu kararı doğurdu?

**Seçenekler:**
- A) ... → artı/eksi
- B) ... → artı/eksi

**Karar:** Seçilen şey.

**Neden:** Hangi kısıta/hedefe dayanarak?

**Tekrar gözden geçir:** Hangi koşul oluşursa bu karar masaya geri gelir?
-->
EOF

echo "✅ Hazır: $HEDEF"
echo "Sıradaki adım: AI aracında projeyi aç ve '/baslat' yaz."
echo "Usta sana soruları sorup PROJECT.md'yi kendisi dolduracak."
