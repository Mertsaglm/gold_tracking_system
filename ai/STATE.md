# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-07-26
**Aktif milestone:** **Karar motoru** (ADR #007) — sistem artık hüküm veriyor,
sırada verdiği hükmün karnesini tutması var

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

**AMAÇ FONKSİYONU: terminal GRAM sayısı** (TL getirisi değil — ADR #007).
Raporun en başında **HÜKÜM** bloğu var; `/hukum` ile Telegram'dan da sorulur.
İki kol: **ÇEKİRDEK** (aylık alım şiddeti, açık) + **TAKTİK** (sat/geri al,
**doğuştan kapalı**). Ölçüldü: satmak 1 ayda ortalama **−1.99% gram**
kaybettiriyor, bir sinyalin tabanı **+3.18p** yenmesi gerek, aşan aday yok.
Ölçüm `reports/gram_engeli.md` + `data/gram_engeli.json` (önbellek).

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
| **Faz C biter bitmez** | Tahmin karnesi saatini başlat | İlk `predictions` satırı yazıldı; 1-ay tahmini ~30 gün sonra çözülecek |
| **Faz C + ~30 çözülmüş tahmin** (≈2026-10, kayıt başlangıcına bağlı) | ⚠️ **TAKTİK KAPI KARARI** | `karne` okundu; şart (N≥30 **ve** gram etkisi>0 **ve** isabet farkı>+10p) sağlandı mı? Sağlandıysa `karar.taktik.aktif: true` + ADR. **Sağlanmadıysa "trade kolu kalıcı kapalı" ADR'si yazılır — bu da bir sonuçtur** |
| **~2026-10** (3 ay yeni veri) | `python -m src.gram engel` tazele | `data/gram_engeli.json` yeni tarihli; taban ve eşikler değişti mi bakıldı |
| **Faz E'den önce** | `chart.validate` faz düzeltmesiyle yeniden koş | `reports/grafik_dogrulama.md` faz-eşleştirmeli tabanla üretildi; eski uzun-ufuk bulguları gözden geçirildi (ADR #007-E) |
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
- 2026-07-26 — **Karar motoru Faz A+B** (DECISIONS #007): `src/gram.py` (gram
  hakemi + faz-düzeltmeli taban), `src/karar.py` (iki kollu hüküm + sert kapı),
  rapor başına HÜKÜM bloğu, `/hukum` komutu, `config.yaml karar:` bölümü.
  En riskli varsayım ("trade ederek gram artırılabilir") ölçüldü ve **düştü**.
- 2026-07-26 — **Karar motoru Faz C**: `src/tahmin.py` (kayıt/giriş/çözüm/karne),
  3 yeni tablo + `trg_predictions_immutable`, `daily_job` adım 3d, `/karne`
  komutu, HÜKÜM bloğunda karne satırı. **Canlı örneklem-dışı kayıt BAŞLADI** —
  ilk çözüm ~2026-07-31 (1 hafta), ~2026-08-22 (1 ay).
- 2026-07-26 — **Karar motoru Faz D**: `src/ozellikler.py` tek giriş noktası
  (41 özellik); `tahmin.kaydet` + `karar.build_karar` ikisi de buraya bağlandı.
  Look-ahead artık yapısal olarak imkânsız; test sızıntı enjekte edilerek
  düşebildiği doğrulandı. EVDS yayın gecikmesi bir kontaminasyonu kapattı
  (reel net mevduat %12.7 → %13.1).
- 2026-07-26 — **Karar motoru Faz E**: `src/tahmin_backfill.py` aday taraması
  (karne DEĞİL — örneklem-içi üst sınır). 458 haftalık asof, 14 aday,
  **hiçbiri +3.18p eşiğini geçemedi.** Taktik kol kapalı kalıyor — sonuç bu.
  `reports/gram_aday_taramasi.md`. **266 test.**

## 🔨 Devam Edenler
- _(yok)_

## 🧱 Bekleyenler (iş değil, zaman)
- Retry etkisi ölçümü → ~07-28
- Prova verisi birikimi → ~09-05 karar
- Z-skor kapısı → ~09-12

## 🎯 Sıradaki 3 İş
1. **İlk canlı çözümü doğrula (~2026-07-31).** DoD: `prediction_outcomes`'ta
   1-hafta tahmini çözülmüş; `gram_carry_kazanc_pct` makul; `/karne` "1 çözülmüş"
   diyor. **Bu, tüm zincirin (kaydet→giriş→çözüm) canlıda ilk kez tam dönüşü.**
2. **Push + ilk Actions koşusunu izle.** 5 commit bekliyor. DoD: Actions yeşil;
   raporda HÜKÜM bloğu var; `data/altin.sql`'de `INSERT INTO predictions`
   satırları görünüyor. **L-002 gereği push öncesi dump satır sayıları
   azalmamış olmalı.**
3. **Faz H — görsel grafik** (matplotlib + sendPhoto), istenirse.
   Faz F (SAT kapısı) kod işi değil, ~Ekim'de karneye bakılıp verilecek karar.
   Faz G (MTF) **askıda**: Faz E hiçbir aday bulamadı, yeni gösterge eklemenin
   ölçülmüş bir gerekçesi yok.

## 📦 Backlog (şimdi değil, unutma da)
- **`chart.measure_edge` faz artefaktı** (ADR #007-E) — taban tek fazdan
  ölçülüyor; yayılım h=63'te 2.6-3.2p, h=126'da 7.5-11.6p, `min_anlamli_fark_puan`
  ise 1.0. Uzun ufuk "zayıf kanıt" bulguları gürültünün içinde. Düzeltme hazır
  (`gram.phase_matched_baseline`), `chart.py`'ye taşınmalı.
- **TÜFE serisi 7 aydır bayat** (`TP.FE.OKTG01` son değer 2025-12-01);
  `evds_job.context` sessizce `enf_bek_12ay`'a düşüyor. Reel net mevduat artık
  **çekirdek kolun kapı değişkeni** → bu sessiz yedeğe düşme görünür olmalı.
- **ALTINS1 gidiş-dönüş %0.40 vs banka hesabı %1.20** (3× ucuz). Taktik kapı
  açılırsa enstrüman seçimi eşiği doğrudan değiştirir (3.18p → 2.38p).
- `prim_series(only_valid=False)` ölü argüman; `weekend=0` koşulu `indicative=0`
  altında fazlalık, 4 yerde tekrarlanıyor.
- **Reel faiz göstergesi kapalı** — FRED ölü, ücretsiz TIPS reel getiri muadili yok.
  FRED geri gelirse kendiliğinden açılır. Panel 6/7 ile çalışıyor, öncelik düşük.
- **Çeyrek priminde sezon düzeltmesi yok** — yıllar süren arşiv ister; düz z sezonu
  anomali sanabilir. Arşiv birkaç yıla ulaşınca yeniden değerlendir.
- `src/backup_db.py` hiçbir yerden çağrılmıyor (elle çalıştırılır); WAL-güvenli
  anlık görüntü için doğru araç olduğundan bilinçli tutuldu.
