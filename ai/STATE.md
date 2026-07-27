# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-07-27
**Aktif milestone:** **Karar motoru** (ADR #007/#008) — ÜRETİMDE. Sırada ilk
canlı koşumun doğrulanması ve karne birikimi var

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
| **2026-07-27 akşamı** (push yapıldıysa) | **İlk hafta içi koşumu doğrula** | `data/altin.sql`'de `history_daily` son satırı **bugün DEĞİL** (asof=T−1 tutuyor); `ohlc_daily`'de bugünün barı yok; `predictions` +6 satır |
| **~2026-07-28** (2-3 gün sonra) | **Retry etkisini ölç** | Yeni CSV satırlarında geçersiz kayıt oranı ölçüldü. %6.9'dan düştüyse ✅; düşmediyse truncgil'e yedek kaynak backlog'a |
| **~2026-08-01** (≈7 prova satırı) | Prova birikimini ilk kez oku | z dağılımı görülebiliyor; `tetiklenir_gun` kaç kez `true` olmuş sayıldı |
| **~2026-09-05** (kapıdan ~1 hafta önce) | ⚠️ **Z TABANI KARARI** — en kritik iş | `data/zskor_prova.jsonl` okundu; z **kayıt** tabanında mı **gün** tabanında mı hesaplanacak karara bağlandı; ADR `ai/DECISIONS.md`'ye yazıldı; kod tek tabanı kullanıyor |
| **~2026-09-12** | 🔔 **KAPI AÇILIŞI** (60 geçerli gün) | prim z + çeyrek z sinyalleri ve `z > 2` bildirimi kendiliğinden devreye girer. Kod hazır, **ek iş yok** — yalnız izle |
| **2026-09-12 → 09-19** | Kapı sonrası ilk hafta izleme | Günlük tavan (6) doluyor mu? z alarmları diğer bildirimleri bastırıyor mu? Gerekirse `alerts.prim_z` eşiği ayarlanır |
| **Faz C biter bitmez** | Tahmin karnesi saatini başlat | İlk `predictions` satırı yazıldı; 1-ay tahmini ~30 gün sonra çözülecek |
| **Gölge kol kararından ÖNCE** | ⚠️ ADR #008-B: karne ölçüm üretemiyor | Gölge kol yapılacak mı karara bağlandı. **Yapılmazsa Ekim'deki kapı kararı ölçüme dayanamaz** — o zaman "kalıcı kapalı" ADR'si ölçüm değil KABUL olarak yazılır ve öyle yazıldığı belirtilir |
| **Faz C + ~30 çözülmüş tahmin** (≈2026-10, kayıt başlangıcına bağlı) | ⚠️ **TAKTİK KAPI KARARI** | `karne` okundu; şart (N≥30 **ve** gram etkisi>0 **ve** isabet farkı>+10p) sağlandı mı? Sağlandıysa `karar.taktik.aktif: true` + ADR. **Sağlanmadıysa "trade kolu kalıcı kapalı" ADR'si yazılır — bu da bir sonuçtur** |
| **~2026-10** (3 ay yeni veri) | `python -m src.gram engel` tazele | `data/gram_engeli.json` yeni tarihli; taban ve eşikler değişti mi bakıldı |
| **Faz E'den önce** | `chart.validate` faz düzeltmesiyle yeniden koş | `reports/grafik_dogrulama.md` faz-eşleştirmeli tabanla üretildi; eski uzun-ufuk bulguları gözden geçirildi (ADR #007-E) |
| **~200 rapora ulaşınca** (≈2027 Şubat) | `reports/` yıl klasörlerine böl | `reports/2026/`, `reports/2027/`; README yolu güncel |

**Kapı tahmini nasıl hesaplandı (2026-07-25):** 16 geçerli gün / 18 takvim günü =
**0.89 gün/gün**. Kalan 44 gün ÷ 0.89 ≈ 49 takvim günü → **~2026-09-12**.
Gerçek ilerleme haftalık pazar raporundaki "Arşiv İlerlemesi" satırından okunur —
**tahmin etme, rapordan oku.**

---

## ✅ Tamamlananlar (detay: `ai/archive/STATE-2026-07.md`)

- **2026-07-07 → 07-26:** inşa Faz 1-7 + çoklu-IDE Usta sistemi + backlog
  kapatma + karar motoru Faz A-H. Hepsi arşivde, tarih tarih.
- **2026-07-27 — Uçtan uca denetim (ADR #008) + PUSH** (`7aa3a18`). Push ÖNCESİ
  denetlendi, iyi oldu: **karne hiçbir şey ölçmüyordu** (kayıtlı hükümlerin hiçbiri
  SAT değil → "tabana fark"/"gram etkisi" piyasadan bağımsız 0.00; taktik kapı
  kendini kilitlemişti), `asof=T−1` garantisi kodda zorlanmıyordu, `daily_job` her
  hatayı yutup Actions'ı yeşil bırakıyordu, hayalet hafta sonu barları kalıcıydı.
  Hepsi düzeltildi. Re-audit 3 eksik daha buldu: `history_daily`'ye bugünün yarım
  satırı yazılmaya devam ediyordu (kaynak kapatıldı), L-005 numarası devir
  paketiyle çakışıyordu (→L-009), kökte L-005…L-008 yoktu (tamamlandı).
  **299 test.** Rebase'te üretim dump'ı kazandı — yerel dump 2890 tick eksikti,
  L-009'un ta kendisi. Devir paketi de tazelendi (4 yeni ders + ADR #003).

## 🔨 Devam Edenler
- _(yok — push Mert'in onayını bekliyor)_

## 🧱 Bekleyenler (iş değil, zaman)
- Retry etkisi ölçümü → ~07-28
- Prova verisi birikimi → ~09-05 karar
- Z-skor kapısı → ~09-12

## 🎯 Sıradaki 3 İş
1. **BU AKŞAMKİ İLK KOŞUMU DOĞRULA (2026-07-27, 15:35 UTC).** Karar motoru
   üretime girdi (`7aa3a18`); bu, düzeltilmiş kodun canlıda ilk çalışması.
   DoD — `git fetch` sonrası dört kontrol:
   (a) `data/altin.sql`'de `history_daily` son satırı **bugün DEĞİL** (asof=T−1
       koruması tuttu); (b) `ohlc_daily`'de bugünün ve hafta sonunun barı yok;
   (c) `grep -c "INSERT INTO predictions(" data/altin.sql` → **6**;
   (d) raporda 🎯 HÜKÜM bloğu ve "karne ÖLÇÜM İÇERMİYOR" satırı var.
   Actions kırmızıysa artık gerçekten arıza demektir (K-6: kritik adım exit 1).
2. **Gölge kol kararı (ADR #008-B).** Kapı kapalıyken kol yalnız TUT ürettiği
   için karne asla ölçüm içeremez — döngü GÖRÜNÜR kılındı ama KIRILMADI.
   Kırmak için "kapı açık olsaydı ne derdim" hükmünü ayrı bir kola kaydetmek
   gerekiyor. DoD: karar verildi ve ADR'ye işlendi (yapmamak da bir karardır).
3. **İlk canlı çözümü doğrula (~2026-08-03).** İlk tahmin bugün asof=2026-07-24
   ile yazılıyor, 1-hafta ufku ~5 işlem günü sonra çözülür. DoD:
   `prediction_outcomes`'ta satır var, `/karne` "1 çözülmüş" diyor. Zincirin
   (kaydet→giriş→çözüm) canlıda ilk tam dönüşü. Faz F ~Ekim'de karneye bakılıp
   verilecek karar; Faz G (MTF) **askıda** (Faz E aday bulamadı).

## 📦 Backlog (şimdi değil, unutma da)
- **`deploy/altin-backup.service` var olmayan `scripts/backup.sh`'ı çağırıyor.**
  Oracle Cloud senaryosu aktive edilirse bu timer patlar. `.gitignore` da
  `data/backups/` için aynı script'e atıf yapıyor.
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
