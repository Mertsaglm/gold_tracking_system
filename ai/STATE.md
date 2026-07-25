# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-07-24
**Aktif milestone:** Canlı işletim + çoklu-IDE taşınabilirlik

## ✅ Tamamlananlar
- Sistem canlı ve üretimde (GitHub Actions; Faz 1-7 teslim — bkz `docs/TESLIMAT-ARSIV.md`)
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

- 2026-07-24 — "toplama kesintiye uğruyor" iddiası araştırıldı: **iddia düştü**
  (toplama hızı 07-08'den beri sabit ~13/gün; %16-17 rakamları 07-21 öncesi eski
  metrikten; 545 dk "kesinti" arıza değil kaynak boşluğu; z-skor düzenli ilerliyor
  16/60). Gerçek kusur yanıltıcı metrik etiketiydi → `classify_gap()` eklendi.
  DECISIONS #005, LESSONS L-003
- 2026-07-24 — Doküman düzeni + GitHub hazırlığı: 7 `TESLIMAT*.md` tek
  `docs/TESLIMAT-ARSIV.md`'de birleştirildi (kök 18→11 dosya; çalışmayan Windows
  komutları ve çözülmüş eksik listeleri atıldı, geri çekilen iddialar korundu).
  README/İZLEME bugünkü gerçeğe hizalandı, `.gitignore` yeniden yazıldı
  (satır-sonu yorum tuzağı düzeltildi), kod docstring'leri güncellendi.
- 2026-07-24 — Şüpheli dosyalar tek tek denetlendi. `scripts/backup.sh` + `backup.ps1`
  **silindi**: işlevi Faz 5'te `data/altin.sql` commit'i devralmıştı, üstelik 2.9 MB
  binary yedek üretip gitignore'da olmadığı için repoya sokuyor ve **onay sormadan
  push ediyordu**. `data/backups/` gitignore'a eklendi (tuzak kapatıldı).
  `deploy/`, collector üçlüsü, `evds_series.json`, `reports/` gerekçeleriyle KORUNDU.

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
- `reports/` günde 1 dosya büyüyor (~365/yıl, ~1.8 MB/yıl). ~200 dosyayı aşınca
  yıl klasörlerine ayır (`reports/2026/`). Şimdi gereksiz (20 dosya).
- `src/backup_db.py` artık hiçbir yerden çağrılmıyor (elle çalıştırılır kaldı);
  WAL-güvenli anlık görüntü için doğru araç olduğundan bilinçli tutuldu.
