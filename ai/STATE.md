# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-07-24
**Aktif milestone:** Canlı işletim + çoklu-IDE taşınabilirlik

## ✅ Tamamlananlar
- Sistem canlı ve üretimde (GitHub Actions; Faz 1-7 teslim — bkz `TESLIMAT-*.md`)
- 2026-07-21 — z-skor kapısı düzeltmesi: gün sayıyor, kayıt değil (commit `71c7ba2`)
- 2026-07-24 — çoklu-IDE Usta sistemi proje köküne kuruldu (AGENTS.md + köprüler + ai/)

## 🔨 Devam Edenler
- _(yok)_

## 🧱 Bloklar / Bekleyenler
- Telegram bildirim geçmişi denetimi — kullanıcının Desktop JSON export'u bekleniyor
- Veri kapsaması ~%62 (Actions cron throttling) — iyileştirme kararı bekliyor

## 🎯 Sıradaki 3 İş
1. Veri kapsaması %62 → Actions throttling'i azalt (cron sıklığı/strateji araştır) —
   DoD: kapsama ölçülür, karar `ai/DECISIONS.md`'ye işlenir
2. Telegram export gelince 🔔 bildirim dökümü + rapor çapraz kontrol —
   DoD: bildirim geçmişi denetlendi, boşluk/çift varsa raporlandı
3. (opsiyonel) Giden mesaj logu: `send_message` → `data/telegram_outbox.jsonl` —
   DoD: her gönderi repoda birikiyor, export bağımlılığı biter

## 📦 Backlog (şimdi değil, unutma da)
- Çeyrek primi sezon-düzeltmeli z-skoru (`notify.py`'de "şimdilik pas")
- FRED reel faiz / DXY verisi şu an boş — kaynak dayanıklılığı
- `Proje Yardımcısı/` alt klasörü artık gereksiz (kök kanonik) — temizlenecek
