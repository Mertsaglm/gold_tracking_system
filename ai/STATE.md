# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-07-24
**Aktif milestone:** Canlı işletim + çoklu-IDE taşınabilirlik

## ✅ Tamamlananlar
- Sistem canlı ve üretimde (GitHub Actions; Faz 1-7 teslim — bkz `TESLIMAT-*.md`)
- 2026-07-21 — z-skor kapısı düzeltmesi: gün sayıyor, kayıt değil (commit `71c7ba2`)
- 2026-07-24 — çoklu-IDE Usta sistemi proje köküne kuruldu (AGENTS.md + köprüler + ai/)
- 2026-07-24 — [#1] veri kapsaması ölçüldü + kaynak-retry eklendi (kapsama %62 = GitHub
  throttling, platform kısıtı; %7 geçersiz kayıt → retry ile düşürüldü). Karar DECISIONS #003
- 2026-07-24 — [#3] giden mesaj logu (outbox JSONL): `send_message` → `data/telegram_outbox.jsonl`,
  archive.yml commit'liyor. 144 test geçiyor

## 🔨 Devam Edenler
- _(yok)_

## 🧱 Bloklar / Bekleyenler
- [#2] Telegram bildirim geçmişi denetimi — kullanıcının Desktop JSON export'u bekleniyor (BLOKLU)

## 🎯 Sıradaki 3 İş
1. Birkaç Actions turu sonra retry etkisini ölç: yeni CSV'de geçersiz kayıt oranı
   %7'den düştü mü + outbox doğru birikiyor mu — DoD: oran ölçüldü, outbox commit'lendi
2. Telegram export gelince 🔔 bildirim dökümü + rapor çapraz kontrol —
   DoD: bildirim geçmişi denetlendi, boşluk/çift varsa raporlandı
3. `Proje Yardımcısı/` alt klasörünü temizle (kök kanonik, gereksiz kopya) —
   DoD: alt klasör kaldırıldı, sistem hâlâ kökten çalışıyor

## 📦 Backlog (şimdi değil, unutma da)
- Çeyrek primi sezon-düzeltmeli z-skoru (`notify.py`'de "şimdilik pas")
- FRED reel faiz / DXY verisi şu an boş — kaynak dayanıklılığı
