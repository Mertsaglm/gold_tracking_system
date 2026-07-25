# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-07-25
**Aktif milestone:** İzleme + **12 Eylül 2026 z-skor kapı açılışına hazırlık**

---

## 🧭 Sistem tek bakışta (yeni bir oturum buradan başlasın)

Altın takip sistemi **GitHub Actions'ta 7/24 kendi kendine çalışıyor**; kullanıcının
hiçbir şey çalıştırması gerekmiyor. İki workflow:

| Workflow | Ritim | Ne yapar |
|---|---|---|
| `archive.yml` | `*/15` yazar, **gerçekte ~13 çalışma/gün** (GitHub throttling — normal) | fiyat çek → CSV → eşik değerlendir → tetikte Telegram → commit |
| `daily.yml` | her gün 15:35 UTC (18:35 TR) | import → EVDS → OHLC → history → **z-skor provası** → rapor → Telegram → commit |

**Sağlık ölçütleri (normal aralık):** kapsama %60-100 · geçersiz kayıt ~%7 (retry
sonrası düşmesi bekleniyor) · uzlaşı paneli **6/7 gösterge** (reel faiz FRED ölü
olduğu için kapalı, bilerek).

**Yerelde çalışmadan önce daima `git pull`** — Actions sürekli commit atıyor
(bkz. LESSONS L-001).

---

## 📅 TAKVİM — neyi ne zaman yapmalıyız

> Tarihler mutlak. Bir işi yaparken DoD'sini doğrula, sonra bu tabloyu güncelle.

| Ne zaman | İş | Bitti sayılır (DoD) |
|---|---|---|
| **Her oturum başı** | `git fetch` + yerel/uzak farkı kontrol et | Yerel güncel; "sistem durdu" teşhisi ham veriye dayanıyor |
| **2026-07-25 akşam** (ilk günlük çalışma) | Yeni adımları üretimde doğrula | Actions commit'inde: `data/zskor_prova.jsonl` **oluştu**, raporda DXY satırı `kaynak DX-Y.NYB` yazıyor, `history` adımı hatasız |
| **~2026-07-28** (2-3 gün sonra) | **Retry etkisini ölç** | Yeni CSV satırlarında geçersiz kayıt oranı ölçüldü. %6.9'dan düştüyse ✅; düşmediyse truncgil'e yedek kaynak backlog'a |
| **~2026-08-01** (≈7 prova satırı) | Prova birikimini ilk kez oku | z dağılımı görülebiliyor; `tetiklenir_gun` kaç kez `true` olmuş sayıldı |
| **~2026-09-05** (kapıdan ~1 hafta önce) | ⚠️ **Z TABANI KARARI** — en kritik iş | `data/zskor_prova.jsonl` okundu; z **kayıt** tabanında mı **gün** tabanında mı hesaplanacak karara bağlandı; ADR `ai/DECISIONS.md`'ye yazıldı; kod tek tabanı kullanıyor |
| **~2026-09-12** | 🔔 **KAPI AÇILIŞI** (60 geçerli gün) | prim z + çeyrek z sinyalleri ve `z > 2` bildirimi kendiliğinden devreye girer. Kod hazır, **ek iş yok** — yalnız izle |
| **2026-09-12 → 09-19** | Kapı sonrası ilk hafta izleme | Günlük tavan (6) doluyor mu? z alarmları diğer bildirimleri bastırıyor mu? Gerekirse `alerts.prim_z` eşiği ayarlanır |
| **~200 rapora ulaşınca** (≈2027 Şubat) | `reports/` yıl klasörlerine böl | `reports/2026/`, `reports/2027/`; README yolu güncel |

**Kapı tahmini nasıl hesaplandı (2026-07-25):** 16 geçerli gün / 18 takvim günü =
**0.89 gün/gün**. Kalan 44 gün ÷ 0.89 ≈ 49 takvim günü → **~2026-09-12**.
Gerçek ilerleme haftalık pazar raporundaki "Arşiv İlerlemesi" satırından okunur —
**tahmin etme, rapordan oku.**

---

## ✅ Tamamlananlar (özet — detay: `ai/archive/STATE-2026-07.md`)
- İnşa dönemi Faz 1-7 bitti, sistem canlı (`docs/TESLIMAT-ARSIV.md`)
- 2026-07-24 — Çoklu-IDE Usta sistemi kuruldu · kaynak-retry · outbox arşivi ·
  Telegram denetimi (kural ihlali yok) · **history_daily 17 gündür donuktu, düzeltildi**
- 2026-07-24 — Doküman düzeni, `.gitignore` onarımı, ölü script temizliği
- 2026-07-25 — **Backlog'un tamamı kapatıldı** (DECISIONS #006): FRED yedeği,
  z-skor kuru provası, çeyrek primi kuralı, tek kaynak eşik. **171 test.**

## 🔨 Devam Edenler
- _(yok)_

## 🧱 Bekleyenler (iş değil, zaman)
- Retry etkisi ölçümü → ~07-28
- Prova verisi birikimi → ~09-05 karar
- Z-skor kapısı → ~09-12

## 🎯 Sıradaki 3 İş
1. Bekleyen 17 dosyayı commit + push et — **DoD:** GitHub'da, Actions yeşil
2. 25 Tem akşamki günlük çalışmada yeni adımları doğrula (takvim satırı 2)
3. ~28 Tem'de retry etkisini ölç (takvim satırı 3)

## 📦 Backlog (şimdi değil, unutma da)
- **Reel faiz göstergesi kapalı** — FRED ölü, ücretsiz TIPS reel getiri muadili yok.
  FRED geri gelirse kendiliğinden açılır. Panel 6/7 ile çalışıyor, öncelik düşük.
- **Çeyrek priminde sezon düzeltmesi yok** — yıllar süren arşiv ister; düz z sezonu
  anomali sanabilir. Arşiv birkaç yıla ulaşınca yeniden değerlendir.
- `src/backup_db.py` hiçbir yerden çağrılmıyor (elle çalıştırılır); WAL-güvenli
  anlık görüntü için doğru araç olduğundan bilinçli tutuldu.
