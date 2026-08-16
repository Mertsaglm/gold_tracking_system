# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-08-16
**Aktif milestone:** **Ons kaynağı onarıldı (ADR #013).** Denetimde bulundu:
`yfinance GC=F` canlı kotasyonu 2026-07-29'daki vade roll'ünde **Aralık kontratına**
atlamış; prim 17 gün 1.25 puan yanlış ölçülmüş ve `|prim|>%1.5` alarmı 4 kez boşuna
Telegram'a gitmiş. Ons artık **Truncgil spot**'tan (gram ile aynı kaynak/zaman
damgası). Kirli 14 gün z tabanından düşüldü → **kapı ~09-16'dan ~10-02'ye kaydı**.
Test 851 → **855**; 7 mutasyon, 7/7 yakalandı.

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
**ikisi de aşılamadı**: taktik **+3.18p** (makas öder), çekirdek **+1.99p** (ödemez).
✅ **Çekirdek kademesi 2026-08-11'de KAPATILDI (ADR #012)** — kuralı üreten
`reel_mevduat > %10` ateşlendiğinde ertelemenin ort. gram kazancı **%-0.64**
(N=22, t=1.03), başa baş 0.00'ın ALTINDA; canlı doğrulama **-%1.55 gram**.
Hüküm artık daima `NORMAL AL` (1.00×); kural yine değerlendirilip "açık olsaydı
0.75× olurdu" diye yazılıyor. **Her iki kol da artık alım/satım planına
DOKUNMUYOR** — sistem ölçemediği hiçbir şeye göre davranmıyor. Ölçüm: `reports/gram_engeli.md`, `reports/gram_aday_taramasi.md`
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
| **2026-08-17 (ilk hafta içi koşum)** | 👤 | 🔴 **ONS DÜZELTMESİNİ ÜRETİMDE DOĞRULA (ADR #013)** | Pazartesi raporunda **prim ≈ −0.5%** (−1.75 DEĞİL) · `|prim|>%1.5` alarmı GELMEDİ · `data/archive/2026-08.csv`'de yeni satırların `ons_usd`'si Truncgil biçiminde (2 ondalık, ör. 4376.71) — float32 artığı (4380.39990234375) varsa düzeltme üretime inmemiştir | ⏳ |
| **2026-08-17** | 👤 | Kirli pencere sınırını doğrula | Pazartesi kayıtları `indicative=0` (kirli DEĞİL); rapordaki geçerli gün sayacı 20'den ilerliyor. İlerlemiyorsa `stats.prim_kirli_pencereler.bitis_utc` fazla ileri kalmış | ⏳ |
| **~2026-11-25 ±3 gün** | 👤 | 🔁 **BİR SONRAKİ COMEX ROLL'Ü** (Aralık→Şubat) | O hafta prim serisinde basamak **YOK** doğrulandı. Varsa Truncgil ons'u da vadeli olmuş demektir → ADR #013 yeniden açılır. (Roll takvimi: yılda 5 — Oca-Mar-May-Tem-Kas) | ⏳ |
| **Her oturum başı** | 🤖 | `git fetch` + yerel/uzak farkı kontrol et | Yerel güncel; "sistem durdu" teşhisi ham veriye dayanıyor (L-001) | ♻️ |
| **Her oturum başı** | 🤖 | ⚠️ `git status` — **commit'lenmemiş kaynak var mı?** | Çalışma ağacında bekleyen `src/` değişikliği YOK, ya da varsa Mert'e soruldu. **Ölçüldü 2026-08-11: ADR #010'un TAMAMI (3 fonksiyon + 2 veri dosyası) 13 gündür commit'lenmemiş, üretimde yok.** Belge "yapıldı" derken repo "yapılmadı" diyordu; `HEAD↔origin` farkına bakmak bunu YAKALAMAZ (§2.5) | ♻️ |
| **2026-10-02 ±3 gün** | 👤 | 🔴 **KAPI GÜNÜ CANLI DOĞRULAMA** — `prim_z` ilk kez ateşlenecek | Kapı açıldığı gün Telegram'a `prim_z` bildirimi GELDİ mi bakıldı. Metni `(|z|<1)` içeriyor; kaçış düzeltmesi (ADR #011) tam bu yolu koruyor ama canlıda hiç ateşlenmedi. Gelmezse `data/alert_state.json → saglik` ve Actions logu | ⏳ |
| **~2026-09-25** | 👤 | ⚠️ **Z TABANI + EŞİK KARARI** — kapıdan ~1 hafta önce, en kritik iş | (1) Taban: kayıt mı gün mü? **08-11 ölçümü: 17/17 provada iki taban aynı kararı verdi** → ilkeye göre seç; ADR #012-F gün tabanını öneriyor (kapı gün sayıyor · gün içi kayıtlar seri korelasyonlu, etkin N'i şişirir · kayıt tabanı Actions throttling'ine rehin). (2) ⚠️ **EŞİK:** provada `|z|>2` **%35** tetikledi (nominal %5), günlük tavan 6 → kapı açılışında z alarmları diğerlerini bastırabilir. `alerts.prim_z` prova dağılımına bakılarak yeniden ölçülmeli. DoD: ADR yazıldı, kod tek tabanı kullanıyor, eşik gerekçeli | ⏳ |
| **~2026-09-30** | 🤖 | 🔔 **KAPI AÇILIŞI** (60 geçerli gün) | prim z + çeyrek z sinyalleri ve `z > 2` bildirimi kendiliğinden devreye girer. Kod hazır, **ek iş yok** | ⏳ |
| **2026-09-30 → 10-07** | 👤 | Kapı sonrası ilk hafta izleme | Günlük tavan (6) doluyor mu? z alarmları diğerlerini bastırıyor mu? Gerekirse `alerts.prim_z` ayarlanır | ⏳ |
| **~2026-10** (≈30 çözülmüş tahmin) | 👤 | ⚠️ **TAKTİK KAPI KARARI** | ⚠️ ADR #012-B'den sonra şart matematiksel olarak SAĞLANAMAZ: kol hiç SAT üretmediği için gram etkisi ≡ 0 kalır. Dolayısıyla o gün verilecek karar "kalıcı kapalı" olacak ve **ölçüm değil KABUL** olarak yazılmalı. Gerçek şart şudur: **önce taktik kola beklenen-kazanç üreticisi bağlanmalı** (bugün yok, sebebi ölçüm — ADR #007-H). Üretici yoksa kapı tartışması açılmaz | ⏳ |
| **~2026-10** (3 ay yeni veri) | 👤 | `python -m src.gram engel` tazele | `data/gram_engeli.json` yeni tarihli; taban ve eşikler değişti mi bakıldı | ⏳ |
| **İlk uygun oturum** | 👤 | `ai/PROFILE.md` eksiklerini doldur | "öğrenmek istedikleri" ve "çalışma alışkanlıkları" alanları dolu (Usta sorup doldurur) | ⏳ |
| **~2027-02** (~200 rapor) | 👤 | `reports/` yıl klasörlerine böl | `reports/2026/`, `reports/2027/`; README yolu güncel | ⏳ |

**Kapı tahmini nasıl hesaplandı (2026-08-16, ADR #013 sonrası):**
Geçerli gün **34 → 20** düştü: 07-29 → 08-16 arası 14 gün `kirli_kaynak` işaretli
(vadeli kontrat roll'ü, z tabanına girmiyor). Hız 0.85 gün/gün → kalan 40 gün ÷ 0.85
≈ 47 takvim günü → **~2026-10-02**. Gerçek ilerleme günlük raporun
"Z-skor: arşiv birikiyor (N/60)" satırından okunur — **tahmin etme, rapordan oku.**

---

## ✅ Tamamlananlar (detay: `ai/archive/STATE-2026-07.md`)

- **2026-07-07 → 07-26:** inşa Faz 1-7 + çoklu-IDE Usta sistemi + backlog
  kapatma + karar motoru Faz A-H. Hepsi arşivde, tarih tarih.
- **2026-08-16 — Ons kaynağı onarıldı: prim 17 gündür yanlış ölçülüyormuş**
  (detay **ADR #013**, ders **L-019**). Mert: *"üretilen tahminler sağlam bir
  şekilde mi üretiliyor?"* Bulunan: `yfinance GC=F` **canlı kotasyonu** 2026-07-29
  vade roll'ünde Aralık kontratına (GCZ26, spot+%1.39) atlamış; `theoretical`
  şişmiş, prim **−1.25 puan** sahte iskonto göstermiş. Dört bağımsız kanıt
  (kırılma anı · kontrat merdiveni · Truncgil spot ons · seviye bandı ±0.15p).
  Üretimdeki zarar: `|prim|>%1.5` alarmı 08-11…08-14'te **4 kez boşuna** gitti;
  07-29 raporu hareketin −%1.41'ini haksız yere "Kapalıçarşı primi"ne yazdı.
  **Hüküm/backtest/grafik ETKİLENMEDİ** — onlar günlük bar'ı (geri-düzeltmeli)
  okuyor. Çözüm: ons → Truncgil spot (gram ile aynı kaynak+zaman damgası),
  yfinance yalnız kur. Kirli 14 gün z tabanından düşüldü çünkü z **genişleyen
  pencere**: bırakılsaydı tespit eşiği 0.25p yerine **1.22p** olurdu (5× sağır)
  ve 2028'de bile düzelmezdi. Kapı ~09-16 → **~10-02**. Test 851 → **855**,
  7/7 mutasyon.
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
  Öncesi: `ai/archive/STATE-2026-08.md`.

## 🔨 Devam Edenler
- _(yok)_

## 🧱 Bekleyenler (iş değil, zaman)
- Prova verisi birikimi → ~09-05 karar
- Z-skor kapısı → ~09-14
- İlk canlı çözüm → ~08-03

## 🎯 Sıradaki 3 İş

> ADR #013 ile ons kaynağı onarıldı. Sıradaki iş **doğrulama**, sonrası bekleme.

1. **🔴 Ons düzeltmesini üretimde doğrula (2026-08-17, ilk hafta içi koşum) — 👤 Mert.**
   Tek gerçek açık iş. Pazartesi raporunda **prim ≈ −0.5%** görünmeli (−1.75 değil)
   ve `|prim|>%1.5` alarmı **gelmemeli**. Gelirse düzeltme üretime inmemiştir:
   `data/archive/2026-08.csv`'de yeni `ons_usd` değerlerine bak — 2 ondalıklıysa
   (4376.71) Truncgil, float32 artığı varsa (4380.39990234375) hâlâ yfinance.
   DoD: TAKVİM'deki iki satır ✅.
2. **Z tabanı + eşik kararı (~2026-09-25) — 👤 Mert.** Artık **temiz** veri üstünde
   verilecek. Prova dosyasının 07-29 → 08-16 arası satırları kirli seriden
   üretildi, o aralık **okunmayacak**. ⚠️ Temiz seride bile `|z|>2` bandı dar
   (`[−0.86, −0.37]`) → eşik kalibrasyonu ayrı iş, kirliliği temizlemek onu çözmedi.
   DoD: ADR yazıldı, kod tek tabanı kullanıyor, eşik gerekçeli.
3. **Z-skor kapısı (~2026-10-02) — 🤖 kendiliğinden.** 20/60 geçerli gün, hız 0.85.
   Kapı açılınca `prim_z` canlıda ilk kez ateşlenebilir. DoD: kapı günü davranış
   TAKVİM'deki satıra göre doğrulandı.

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
