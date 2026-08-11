# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-08-11
**Aktif milestone:** **Bildirim hattı onarıldı ve ÜRETİMDE doğrulandı**
(ADR #011, L-018). 2026-07-29 → 08-10 arası hiçbir anomali bildirimi gitmemişti
(125 koşu, hepsi yeşil); `9ebf868` sonrası üretim koşumu **"2 tetik, 2 gönderildi,
0 HATA"** dedi — 13 günlük sessiz kesinti bitti.
Sırada **karne tabanı kararı** — karne hâlâ yapısal olarak hiçbir şey ölçmüyor.

---

## 🧭 Sistem tek bakışta (yeni bir oturum buradan başlasın)

Altın takip sistemi **GitHub Actions'ta 7/24 kendi kendine çalışıyor**; kullanıcının
hiçbir şey çalıştırması gerekmiyor. İki workflow:

| Workflow | Ritim | Ne yapar |
|---|---|---|
| `archive.yml` | `*/15` yazar, **gerçekte ~13 çalışma/gün** (GitHub throttling — normal) | fiyat çek → CSV → eşik değerlendir → tetikte Telegram → commit |
| `daily.yml` | her gün 15:35 UTC (18:35 TR) | import → EVDS → OHLC → history → **z-skor provası** → rapor → Telegram → commit |

**Sağlık ölçütleri (normal aralık):** kapsama %60-100 · geçersiz kayıt ~%7 (retry
sonrası düşmesi bekleniyor — ölçüldü 07-29: **düşmedi**) · uzlaşı paneli
**5/7 gösterge** (ölçüldü 2026-07-29, son 14 rapor: reel faiz FRED **14/14**
ölü — bilerek yedeksiz; Google Trends **12/14** ölü — pytrends 429).

🔔 **Bildirim hattı sağlığı artık RAPORDA.** `notify` ardışık gönderim hatasını
`data/alert_state.json → saglik` altına yazar; günlük rapor arıza varsa en üste
**"🔴 BİLDİRİM HATTI ARIZALI: N ardışık gönderim hatası … GİTMİYOR"** basar.
Rapor bu satırı basıyorsa Actions loguna bakılacak — sessiz kesinti sınıfı
kapatıldı (ADR #011). Satır yoksa hat sağlıklıdır.

**Regresyon zırhı (ADR #009):** `.venv/bin/python -m pytest -q` → **800+ test**.
Bir testi susturmadan önce oku: çoğu bir ADR'yi ya da dersi kilitliyor.
Kırmızı bir "KİLİT TEST" neredeyse daima haklıdır.

**AMAÇ FONKSİYONU: terminal GRAM sayısı** (TL getirisi değil — ADR #007).
Raporun en başında **HÜKÜM** bloğu var. İki kol: **ÇEKİRDEK** (aylık alım
şiddeti, AÇIK) + **TAKTİK** (sat/geri al, **doğuştan kapalı**).
Ölçüldü: satmak 1 ayda ortalama **−1.99% gram** kaybettiriyor. İki eşik var ve
**ikisi de aşılamadı** (ADR #010-B): taktik **+3.18p** (makas öder), çekirdek
**+1.99p** (ödemez). Çekirdek kademesini üreten `reel_mevduat > %10` kuralı
**+1.34p** (N=22, t=1.03) → kendi eşiğinin ALTINDA; hüküm bloğu bunu her gün
beyan ediyor. Ölçüm: `reports/gram_engeli.md`, `reports/gram_aday_taramasi.md`
+ `data/gram_engeli.json`, `data/aday_taramasi.json` (önbellek).

**GRAFİK (ADR #010-A):** `chart.measure_edge` tabanı artık TÜM fazlardan ölçer;
eşik faz yayılımından küçük olamaz. Yeniden ölçüldü → **"zayıf kanıt" 10 → 1**,
"kenar yok" 14 → 23. Faz yayılımı 1ay 1.0p · 3ay 4.1p · 6ay 7.4p. **Grafiğin
ölçülmüş yön kenarı YOK** — seviyeler kademe/stop geometrisi, yön iddiası değil.

⚠️ **Telegram komutları üretimde YANIT VERMEZ** (`/hukum` `/karne` `/grafik`...).
Actions push-only; komutlar `run_bot` long-polling ister ve o hiçbir yerde
koşmuyor. README bunu yazıyor, ama `telegram_chat.json` gösteriyor ki Mert
3 kez komut yazıp (2026-07-09 ×2, 07-26) hiç cevap alamamış.

**Yerelde çalışmadan önce daima `git pull`** — Actions sürekli commit atıyor
(bkz. LESSONS L-001).

---

## 📅 TAKVİM & 👤 SENDE KALANLAR — neyi ne zaman, KİM yapacak

> Tarihler mutlak. Bir iş bitince **Durum'u ✅ + tarih** yap; ertelenirse tarihi
> güncelle ve **sebebini yaz** — sessizce silme.
>
> **Kim:** 👤 = yalnız Mert yapabilir (karar, onay, dışarıdan doğrulama).
> 🤖 = sistem kendiliğinden yapar ya da Usta yapar, Mert'ten bir şey beklenmez.
>
> ⚠️ **Usta'ya kural (AGENTS.md §2):** her oturumun başında bu tabloda
> **Kim=👤, tarihi gelmiş/geçmiş ve Durum=⏳** olan her satırı Mert'e AÇIKÇA sor.
> Bunlar Usta'nın yerine yapamayacağı işlerdir; sorulmazsa unutulur ve proje durur.

| Ne zaman | Kim | İş | Bitti sayılır (DoD) | Durum |
|---|:--:|---|---|:--:|
| **Her oturum başı** | 🤖 | `git fetch` + yerel/uzak farkı kontrol et | Yerel güncel; "sistem durdu" teşhisi ham veriye dayanıyor (L-001) | ♻️ |
| **Her oturum başı** | 🤖 | ⚠️ `git status` — **commit'lenmemiş kaynak var mı?** | Çalışma ağacında bekleyen `src/` değişikliği YOK, ya da varsa Mert'e soruldu. **Ölçüldü 2026-08-11: ADR #010'un TAMAMI (3 fonksiyon + 2 veri dosyası) 13 gündür commit'lenmemiş, üretimde yok.** Belge "yapıldı" derken repo "yapılmadı" diyordu; `HEAD↔origin` farkına bakmak bunu YAKALAMAZ (§2.5) | ♻️ |
| **2026-07-29** | 👤 | ⚠️ **KADEME KARARI** (ADR #010-B) — açık kolun kuralı kendi eşiğini geçemiyor | Karar verildi: `karar.cekirdek` kademesi (0.75×/1.25×) **kalsın mı, 1.0×'a mı düşsün**? Ölçüm: kural +1.34p, başa baş +1.99p, t=1.03. Kalırsa "ölçülmemiş ama küçük ve simetrik, tutuyoruz" ADR'si; kalkarsa `kademe_carpani_*: 1.0`. **Yapmamak da karardır ama YAZILMALI** | ⏳ |
| **2026-07-29** | 👤 | **Telegram komutları kararı** | `/hukum` `/karne` `/grafik` üretimde yanıt vermiyor (push-only). Üç seçenekten biri seçildi: (a) kabul + PROJECT.md/README'de net uyarı, (b) `archive.yml`'a "bekleyen komutları yanıtla" adımı (gecikme ≤ ~3 saat), (c) komutları kapsamdan çıkar | ⏳ |
| **~2026-08-01** | 👤 | Prova birikimini ilk kez oku (≈7 satır) | z dağılımı görülebiliyor; `tetiklenir_gun` kaç kez `true` olmuş sayıldı | ⏳ |
| **2026-08-11** | 👤 | ⚠️ **KARNE TABANI KARARI** (denetimden çıktı, ADR #010-B/#008-B ile aynı kök) | Çekirdek kolun tabanı "hep TUT" olduğu için `gram_etkisi` 8/8 çözümde **0.000**; 60 tahminin 60'ı aynı. Taban **"hep 1.0× al"** yapılırsa kademenin gerçek gram bedeli ölçülür (07-27→08-10 penceresinde **−%1.55**). Karar: taban değişsin mi? | ⏳ |
| **2026-09-14 ±3 gün** | 👤 | 🔴 **KAPI GÜNÜ CANLI DOĞRULAMA** — `prim_z` ilk kez ateşlenecek | Kapı açıldığı gün Telegram'a `prim_z` bildirimi GELDİ mi bakıldı. Metni `(|z|<1)` içeriyor; kaçış düzeltmesi (ADR #011) tam bu yolu koruyor ama canlıda hiç ateşlenmedi. Gelmezse `data/alert_state.json → saglik` ve Actions logu | ⏳ |
| ~~2026-08-03~~ | 👤 | ~~İlk canlı çözümü doğrula~~ | **Ölçüldü 08-11:** `prediction_outcomes`=8 satır, zincir (kaydet→giriş→çözüm) canlıda tam döndü. `gram_carry_kazanc_pct` −4.87…+0.16 aralığında, makul. ⚠️ Ama `gram_etkisi` 8/8 **0.000** → yukarıdaki taban kararı | ✅ 08-11 |
| **~2026-09-05** | 👤 | ⚠️ **Z TABANI KARARI** — kapıdan ~1 hafta önce, en kritik iş | `data/zskor_prova.jsonl` okundu; z **kayıt** tabanında mı **gün** tabanında mı hesaplanacak karara bağlandı; ADR yazıldı; kod tek tabanı kullanıyor | ⏳ |
| **~2026-09-12** | 🤖 | 🔔 **KAPI AÇILIŞI** (60 geçerli gün) | prim z + çeyrek z sinyalleri ve `z > 2` bildirimi kendiliğinden devreye girer. Kod hazır, **ek iş yok** | ⏳ |
| **2026-09-12 → 09-19** | 👤 | Kapı sonrası ilk hafta izleme | Günlük tavan (6) doluyor mu? z alarmları diğerlerini bastırıyor mu? Gerekirse `alerts.prim_z` ayarlanır | ⏳ |
| **~2026-10 (ÖNCE)** | 👤 | ⚠️ **GÖLGE KOL KARARI** (ADR #008-B) — karne ölçüm üretemiyor | Gölge kol yapılacak mı karara bağlandı. **Yapılmazsa Ekim'deki kapı kararı ölçüme dayanamaz**; o zaman "kalıcı kapalı" ADR'si ölçüm değil **KABUL** olarak yazılır ve öyle yazıldığı belirtilir | ⏳ |
| **~2026-10** (≈30 çözülmüş tahmin) | 👤 | ⚠️ **TAKTİK KAPI KARARI** | `karne` okundu; şart (N≥30 **ve** gram etkisi>0 **ve** isabet farkı>+10p) sağlandı mı? Sağlandıysa `karar.taktik.aktif: true` + ADR. Sağlanmadıysa "trade kolu kalıcı kapalı" ADR'si — **bu da bir sonuçtur** | ⏳ |
| **~2026-10** (3 ay yeni veri) | 👤 | `python -m src.gram engel` tazele | `data/gram_engeli.json` yeni tarihli; taban ve eşikler değişti mi bakıldı | ⏳ |
| **İlk uygun oturum** | 👤 | `ai/PROFILE.md` eksiklerini doldur | "öğrenmek istedikleri" ve "çalışma alışkanlıkları" alanları dolu (Usta sorup doldurur) | ⏳ |
| **~2027-02** (~200 rapor) | 👤 | `reports/` yıl klasörlerine böl | `reports/2026/`, `reports/2027/`; README yolu güncel | ⏳ |
| ~~2026-07-25 akşam~~ | 👤 | ~~Yeni adımları üretimde doğrula~~ | `zskor_prova.jsonl` oluştu, DXY `DX-Y.NYB`, `history` hatasız | ✅ 07-25 |
| ~~Faz C biter bitmez~~ | 🤖 | ~~Tahmin karnesi saatini başlat~~ | Kod üretimde (`7aa3a18`); ilk `predictions` satırları 07-27 akşamı yazılacak | ✅ 07-27 |
| ~~2026-07-27 akşamı~~ | 👤 | ~~İlk hafta içi koşumu doğrula~~ | 5/5 geçti: `history_daily` son 07-27 · hafta sonu barı yok · `predictions`=12 (2 koşum × 6) · HÜKÜM + karne satırı var · `ticks`=1799 | ✅ 07-29 |
| ~~2026-07-27 akşamı~~ | 👤 | ~~Tick tekilliğini canlıda doğrula~~ | 1663 → **1799** (+136, gün başına ~70); sıçrama yok, kısıt tuttu. Dump 19 694 satır | ✅ 07-29 |
| ~~~2026-07-28~~ | 👤 | ~~Retry etkisini ölç~~ | **Ölçüldü, İDDİA DÜŞTÜ:** tüm kayıt %6.93 → %6.67 (4/60). 20 geçersiz kaydın 20'sinde truncgil'in 8 alanı BİRDEN boş, yfinance hiç düşmedi → kesinti 3×4 sn retry'dan uzun. Yedek kaynak Backlog'a | ✅ 07-29 |
| ~~Backlog'dan çıkınca~~ | 👤 | ~~`chart.validate`'i faz düzeltmesiyle yeniden koş~~ | Düzeltme koda taşındı + yeniden ölçüldü: "zayıf kanıt" 10 → 1 (ADR #010-A) | ✅ 07-29 |

**Kapı tahmini nasıl hesaplandı (2026-08-11 tazelendi, üretim DB'sinden ölçüldü):**
**30/60 geçerli gün**. 2026-07-07 → 08-10 = 35 takvim günü → hız **0.857 gün/gün**
(07-29'daki 0.86 ölçümüyle birebir aynı — ritim stabil). Kalan 30 gün ÷ 0.857 ≈ 35
takvim günü → **~2026-09-14** (tahmin değişmedi). Gerçek ilerleme günlük raporun
"Z-skor: arşiv birikiyor (N/60)" satırından okunur — **tahmin etme, rapordan oku.**

---

## ✅ Tamamlananlar (detay: `ai/archive/STATE-2026-07.md`)

- **2026-07-07 → 07-26:** inşa Faz 1-7 + çoklu-IDE Usta sistemi + backlog
  kapatma + karar motoru Faz A-H. Hepsi arşivde, tarih tarih.
- **2026-08-11 — Derin denetim + bildirim hattı onarıldı** (detay **ADR #011**,
  ders **L-018**, rapor `ai/denetim-2026-08-11.md`). Mert: "uzun zamandır kendi
  çalışıyor, kaliteli sonuç üretebilmiş mi?" Ölçülenler: (a) uptime %99.7, 34/35
  gün rapor; (b) **13 gün / 125 koşu boyunca hiçbir anomali bildirimi gitmemiş** —
  kaçırılmamış `<`, canlı Telegram deneyiyle doğrulandı (400 → 200); (c) 08-06
  günlük raporu concurrency yüzünden **iptal edilmiş**, günün tamamı kayıp;
  (d) karne yapısal 0 (60/60 aynı hüküm, `gram_etkisi` 8/8 sıfır) ve 0.75×
  kademenin gram bedeli **−%1.55** ölçüldü; (e) hafta sonu beklentisi **tabanı
  yeniyor** (MAE 0.52p vs 1.12p, sistematik −0.38p sapma); (f) kademe kanıtı
  satırı üretimde hiç basılmamış. Test 815 → **839**; 6 mutasyon, **6/6 yakalandı**.
- **2026-07-29 — Grafik ölçümü faz artefaktından arındırıldı** — ADR **#010**,
  ders L-016. "Zayıf kanıt" 10 → 1; grafiğin ölçülmüş yön kenarı YOK.
- **2026-07-27 — Regresyon zırhı** — ADR **#009**, dersler L-013/L-014/L-015.
  299 → 800+ test, ağırlık merkezi sözleşme; 20/20 mutasyon yakalandı.
- **2026-07-27 — Uçtan uca denetim + ilk PUSH** (`7aa3a18`) — ADR **#008**,
  dersler L-010/L-011.

## 🔨 Devam Edenler
- _(yok)_

## 🧱 Bekleyenler (iş değil, zaman)
- Prova verisi birikimi → ~09-05 karar
- Z-skor kapısı → ~09-14
- İlk canlı çözüm → ~08-03

## 🎯 Sıradaki 3 İş
1. **Karne tabanı + kademe kararı (ADR #010-B) — 👤 Mert.** İkisi tek karar oldu.
   Denetim ölçtü: çekirdek kol 30/30 `AL_AZ` üretti, altın aynı dönemde **%+9.55**
   koştu, 0.75× kademenin gram bedeli **−%1.55** — ve karne bunu **0.000** yazdı,
   çünkü tabanı "hep TUT". Seçenekler: (a) taban "hep 1.0× al" yapılsın → karne
   ilk kez gerçek bir şey ölçer; (b) `kademe_carpani_ust/alt: 1.0` → sistem
   ölçemediği sürece alım planına dokunmasın; (c) kademe kalsın + "ölçülmemiş ama
   dar, tutuyoruz" ADR'si. DoD: karar ADR'ye işlendi. **Yapmamak da karardır.**
   _Not: "Kademenin kanıtı" satırı artık üretimde gerçekten basılıyor (ADR #011) —
   07-29 → 08-10 arası 7/7 raporda YOKTU, dosya commit'lenmemişti._
2. **Gölge kol kararı (ADR #008-B).** Kapı kapalıyken kol yalnız TUT ürettiği
   için karne asla ölçüm içeremez — döngü GÖRÜNÜR kılındı ama KIRILMADI.
   Kırmak için "kapı açık olsaydı ne derdim" hükmünü ayrı bir kola kaydetmek
   gerekiyor. DoD: karar verildi ve ADR'ye işlendi (yapmamak da bir karardır).
   _Not: #010-B ile aynı kökten — ikisi de "ölçemediğim şeyi nasıl raporlarım"._
3. **İlk canlı çözümü doğrula (~2026-08-03).** İlk tahmin asof=2026-07-24 ile
   yazıldı, 1-hafta ufku ~5 işlem günü sonra çözülür. DoD:
   `prediction_outcomes`'ta satır var, karne "1 çözülmüş" diyor. Zincirin
   (kaydet→giriş→çözüm) canlıda ilk tam dönüşü. Faz F ~Ekim'de karneye bakılıp
   verilecek karar; Faz G (MTF) **askıda** (Faz E aday bulamadı).

## 📦 Backlog (şimdi değil, unutma da)
- **Truncgil'e yedek kaynak** (2026-07-29 ölçümü) — geçersiz kayıtların %100'ü
  truncgil'in TAM kesintisi; retry (3×4 sn) yetişmiyor, oran %6.9'da sabit.
  Yedek bir gram/çeyrek kaynağı z-skor kapısını öne çeker. Öncelik: orta.
- **`RSI aşırı satım · 1ay · +2.0p`** — faz düzeltmesinden sonra ayakta kalan
  TEK grafik satırı (N=16, in-sample ve OOS ikisi de "ölçüm yetersiz").
  54 karşılaştırmada 1 zayıf satır = Bonferroni'den sonra kanıt değil. Arşiv
  büyüyünce yeniden ölçülsün; aday taramasına eklemek için henüz erken.
- **TÜFE serisi 8 aydır bayat** (`TP.FE.OKTG01` son değer 2025-12-01, ölçüldü 08-11);
  ⚠️ **duyarlılık ölçüldü:** çekirdek kolun kapı değişkeni beklentiyle %12.85
  (→ AZ AL), gerçekleşen TÜFE ile %6.87 (→ **NORMAL AL**). Hüküm tamamen bu seri
  seçimine bağlı ve rapor hangisini kullandığını söylemiyor. Dönmesi için beklenti
  > %27.17 (şu an 23.95) ya da brüt mevduat < %42.76 (şu an 46.92) gerekiyor.
  `evds_job.context` sessizce `enf_bek_12ay`'a düşüyor. Reel net mevduat artık
  **çekirdek kolun kapı değişkeni** → bu sessiz yedeğe düşme görünür olmalı.
- **ALTINS1 gidiş-dönüş %0.40 vs banka hesabı %1.20** (3× ucuz). Taktik kapı
  açılırsa enstrüman seçimi eşiği doğrudan değiştirir (3.18p → 2.38p).
- `weekend=0` koşulu `indicative=0` altında fazlalık, 4 yerde tekrarlanıyor
  (bilinçli savunma katmanı; `db.py` docstring'inde gerekçesi yazılı).
- **Reel faiz göstergesi kapalı** — FRED ölü, ücretsiz TIPS reel getiri muadili yok.
  FRED geri gelirse kendiliğinden açılır. Öncelik düşük.
- **Google Trends 12/14 gün ölü** (pytrends 429 — Google rate-limit). Panel bu
  yüzden 6/7 değil **5/7** çalışıyor. Gösterge paydadan düşüyor (uydurma yok),
  ama iki kör gösterge uzlaşı skorunu 5 oya indiriyor. Yedek: Trends'i haftalık
  çekip önbelleğe almak (günlük 429'a takılıyor, haftalık takılmayabilir).
- **Çeyrek priminde sezon düzeltmesi yok** — yıllar süren arşiv ister; düz z sezonu
  anomali sanabilir. Arşiv birkaç yıla ulaşınca yeniden değerlendir.
- `src/backup_db.py` hiçbir yerden çağrılmıyor (elle çalıştırılır); WAL-güvenli
  anlık görüntü için doğru araç olduğundan bilinçli tutuldu.
