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
- 2026-07-24 — [#2] Telegram export denetlendi: 21 alarm + 24 rapor, soğuma/tavan/
  hafta-sonu-bastırma kuralları ihlalsiz, rapor↔repo %100 eşleşti
- 2026-07-24 — İÇERİK denetimi: `history_daily` 17 gündür donuktu (07-07'de kalmış,
  hiçbir otomatik iş beslemiyordu) → ATR/günlük-hareket alarmları 17 gün yanlış
  eşikle çalışıyordu. `history.update_recent()` yazıldı, daily_job'a bağlandı,
  canlı DB'de doğrulandı (ATR 75→80.5), dump commit'lendi. DECISIONS #004, LESSONS L-002

## 🔨 Devam Edenler
- _(yok)_

## 🧱 Bloklar / Bekleyenler
- _(yok)_

## 🎯 Sıradaki 3 İş
1. Bir sonraki Actions günlük çalışmasında `history` adımının log'da hatasız
   geçtiğini doğrula — DoD: `daily_job` sonucunda `result["history"]["rows"]>0` veya 0 (güncel)
2. `telegram çıktısı.json` kökte, git'e eklenmemiş — public repo'ya gitmemesi için
   gitignore'a mı alınsın, kullanıcı karar versin — DoD: karar alındı, uygulandı
3. `Proje Yardımcısı/` alt klasörünü temizle (kök kanonik, gereksiz kopya) —
   DoD: alt klasör kaldırıldı, sistem hâlâ kökten çalışıyor

## 📦 Backlog (şimdi değil, unutma da)
- Çeyrek primi sezon-düzeltmeli z-skoru (`notify.py`'de "şimdilik pas")
- FRED reel faiz / DXY verisi şu an boş — kaynak dayanıklılığı
