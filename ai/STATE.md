# STATE.md — Mevcut Durum

> Usta her oturumun başında bu dosyayı okur, sonunda günceller.
> KISA TUT: ~100 satırı aşınca eskiyi `ai/archive/STATE-YYYY-MM.md`'ye taşı.

**Son güncelleme:** 2026-08-28
**Aktif milestone:** **🔴 PRİM ÖLÇÜM TAŞIMIYOR — ADR #013 onu bir KİMLİĞE çevirmiş
(ADR #014, ders L-020).** İki bağımsız denetim raporu (Claude + GPT, 25 Ağu)
uygulama turunda doğrulandı. Bulunan: ons ile gram aynı satıcıya taşınınca ons
prim formülünde **sadeleşiyor** → 08-17'den beri prim'in **%99.81'i** yalnız iki
USD beslemesinin oranı (düzeltme öncesi %18.2). Saf-Truncgil tabanında prim her
gün **tam −0.5000%**; 08-22'de gün-içi varyans **tam sıfır**.
**Bağımsızlık nöbetçisi** eklendi → kimliğe düşen 11 gün kapı sayacının dışında,
geçerli gün **30 → 19**. Kapı, bağımsız ons kaynağı kararı verilene kadar
**ilerlemiyor**. Test 855 → **872**; 13 mutasyon, 13/13 yakalandı.

⚠️ **Bu turda DÜZELTİLEN yanlış belge iddiaları:**
- ~~"17/17 provada iki taban aynı kararı verdi"~~ → yalnız **prim** kanalı için
  doğru (0/34). **Çeyrek kanalında 6/34 uyuşmazlık** var (B-08).
- ~~"gerçekte ~13 çalışma/gün"~~ → 08-26'da **24**, 08-25'te ~30 koşum/gün.
  Ama 08-27 ve 08-28'de **yalnız 2/gün** — canlı Actions throttling olayı, aşağıda.

---

## 🧭 Sistem tek bakışta (yeni bir oturum buradan başlasın)

Altın takip sistemi **GitHub Actions'ta 7/24 kendi kendine çalışıyor**; kullanıcının
hiçbir şey çalıştırması gerekmiyor. İki workflow:

| Workflow | Ritim | Ne yapar |
|---|---|---|
| `archive.yml` | `*/15` yazar, gerçekte **dalgalı**: 08-26'da 24, **08-27/28'de yalnız 2/gün** (Actions cron throttling — ölçüldü 08-28, izlenecek) | fiyat çek → CSV → eşik değerlendir → tetikte Telegram → commit |
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
| ~~2026-08-17~~ | 👤 | ~~ONS DÜZELTMESİNİ ÜRETİMDE DOĞRULA (ADR #013)~~ | ✅ **Doğrulandı 2026-08-28:** kaynak üretime indi (yeni `ons_usd` 2 ondalıklı, prim −0.49%, alarm gelmedi). **AMA düzeltme prim'i ÖLÇÜM OLMAKTAN ÇIKARDI** → ADR #014 | ✅ 08-28 |
| **AÇIK — 1 numaralı iş** | 👤 | 🔴 **BAĞIMSIZ ONS KAYNAĞI KARARI (ADR #014-C)** | Yeni kaynak devrede · 10 gün toplandı · **bağımsızlık nöbetçisi ateşlemiyor** (gün-içi CV > 1e-4) · kapı sayacı yeniden ilerliyor | ⏳ |
| ~~2026-08-17~~ | 👤 | ~~Kirli pencere sınırını doğrula~~ | ✅ **Ölçüldü 08-28:** sınır doğru, sayaç 20→30 ilerledi. Ama 08-17 sonrası 11 gün artık `turetilmis` işaretli (ADR #014) → **19**'a düştü | ✅ 08-28 |
| **~2026-11-25 ±3 gün** | 👤 | 🔁 **BİR SONRAKİ COMEX ROLL'Ü** (Aralık→Şubat) | O hafta prim serisinde basamak **YOK** doğrulandı. Varsa Truncgil ons'u da vadeli olmuş demektir → ADR #013 yeniden açılır. (Roll takvimi: yılda 5 — Oca-Mar-May-Tem-Kas) | ⏳ |
| **Her oturum başı** | 🤖 | `git fetch` + yerel/uzak farkı kontrol et | Yerel güncel; "sistem durdu" teşhisi ham veriye dayanıyor (L-001) | ♻️ |
| **Her oturum başı** | 🤖 | ⚠️ `git status` — **commit'lenmemiş kaynak var mı?** | Çalışma ağacında bekleyen `src/` değişikliği YOK, ya da varsa Mert'e soruldu. **Ölçüldü 2026-08-11: ADR #010'un TAMAMI (3 fonksiyon + 2 veri dosyası) 13 gündür commit'lenmemiş, üretimde yok.** Belge "yapıldı" derken repo "yapılmadı" diyordu; `HEAD↔origin` farkına bakmak bunu YAKALAMAZ (§2.5) | ♻️ |
| ~~2026-10-02~~ **TARİH GEÇERSİZ** (sayaç 19/60'ta durdu) | 👤 | 🔴 **KAPI GÜNÜ CANLI DOĞRULAMA** — `prim_z` ilk kez ateşlenecek | Kapı açıldığı gün Telegram'a `prim_z` bildirimi GELDİ mi bakıldı. Metni `(|z|<1)` içeriyor; kaçış düzeltmesi (ADR #011) tam bu yolu koruyor ama canlıda hiç ateşlenmedi. Gelmezse `data/alert_state.json → saglik` ve Actions logu | ⏳ |
| ~~2026-09-25~~ **1'den SONRA** | 👤 | ⚠️ **Z TABANI + EŞİK KARARI** — kapıdan ~1 hafta önce, en kritik iş | (1) Taban: kayıt mı gün mü? **08-11 ölçümü: 17/17 provada iki taban aynı kararı verdi** → ilkeye göre seç; ADR #012-F gün tabanını öneriyor (kapı gün sayıyor · gün içi kayıtlar seri korelasyonlu, etkin N'i şişirir · kayıt tabanı Actions throttling'ine rehin). (2) ⚠️ **EŞİK:** provada `|z|>2` **%35** tetikledi (nominal %5), günlük tavan 6 → kapı açılışında z alarmları diğerlerini bastırabilir. `alerts.prim_z` prova dağılımına bakılarak yeniden ölçülmeli. ⚠️ Öncülü çürüdü: "17/17 iki taban aynı" yalnız PRİM için doğru, çeyrekte **6/34 uyuşmazlık** (ölçüldü 08-28). DoD: ADR yazıldı, kod tek tabanı kullanıyor, eşik gerekçeli | ⏳ |
| **belirsiz — 1'e bağlı** | 🤖 | 🔔 **KAPI AÇILIŞI** (60 geçerli gün) | prim z + çeyrek z sinyalleri ve `z > 2` bildirimi kendiliğinden devreye girer. Kod hazır, **ek iş yok** | ⏳ |
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
- **2026-08-11 → 08-16:** derin denetim + bildirim hattı onarımı (ADR #011,
  L-018) ve ons kaynağı roll düzeltmesi (ADR #013, L-019). Detay:
  `ai/archive/STATE-2026-08.md` + `ai/denetim-2026-08-11.md`.
- **2026-08-28 — İki denetim raporu uygulandı; prim'in ölçüm taşımadığı bulundu**
  (detay **ADR #014**, ders **L-020**). 25 Ağu'da üretilen Claude + GPT raporları
  doğrulama turundan geçirildi. Ana bulgu: ADR #013'ün düzeltmesi prim'i bir
  KİMLİĞE çevirmiş (ons sadeleşiyor; varyansın %99.81'i iki USD beslemesinin
  oranı). İki rapor bu olguyu ZIT okumuştu — ölçümle ayrıldı, Claude haklı çıktı.
  Eklenenler: bağımsızlık nöbetçisi · rejim dejenerelik kapısı (rejim satırı
  48/48 raporda tabanın birebir kopyasıymış) · `notify` takvim+bayatlık kapısı
  (3 kanıtlanmış yanlış Pazartesi bildirimi) · GMA paneli DB'den · panel tek
  hesap · `daily_job` adım hataları raporda · **CI workflow'u** (864 test
  GitHub'da hiç koşmuyormuş). Test 855 → **872**; 13 mutasyon, 13/13 yakalandı.

## 🔨 Devam Edenler
- _(yok)_

## ⚠️ İZLENECEK — canlı olay (2026-08-28)
`archive.yml` koşum sayısı 08-26'da 24/gün iken **08-27 ve 08-28'de 2/gün**e
düştü. Koşumlar BAŞARISIZ değil, hiç **tetiklenmiyor** (GitHub cron throttling);
`gh run list` hepsini `success` gösteriyor. Günlük rapor bunu "~6 ardışık çalışma
başarısız" diye yazıyor — **kelime yanlış** (başarısız değil, koşmadı).
Gün sayacı etkilenmiyor (gün başına 2 kayıt da o günü sayar) ama gün-içi ölçüm
gücü düşüyor: bağımsızlık nöbetçisi 5 kayıttan az günde hüküm veremiyor.
İki gün daha sürerse bakılacak.

## 🧱 Bekleyenler (iş değil, zaman)
- Prova verisi birikimi → ~09-05 karar
- Z-skor kapısı → ~09-14
- İlk canlı çözüm → ~08-03

## 🎯 Sıradaki 3 İş

> ADR #014 ile prim'in ölçüm taşımadığı kanıtlandı. Sıradaki iş **kaynak kararı**;
> o verilmeden kapı, z eşiği ve prim alarmları anlamsız.

1. **🔴 ONS KAYNAĞI KARARI — 👤 Mert, en kritik iş.** Prim'in ölçüm olabilmesi için
   teorik bacağın **bağımsız** bir kaynaktan gelmesi şart. Öneri: ons bağımsız bir
   spot kaynaktan (stooq `XAUUSD` gibi), kur ise Truncgil'in kendi `usd_mid`'inden
   (gram ile aynı zaman damgası) — böylece ons bağımsız, kur senkron olur.
   ⚠️ Yan fayda: bugün prim varyansının %99.81'i olan kur-beslemesi farkı da
   kapanır. DoD: ADR yazıldı, 10 gün toplandı, **nöbetçi ateşlemiyor**.
2. **Z tabanı + eşik kararı — 👤 Mert, 1'den SONRA.** ⚠️ Eski tarih (~09-25)
   geçersiz: taban artık yok. Kalan 19 geçerli günün tamamı eski yfinance
   rejiminden ve o rejim yenisiyle **aynı dağılım değil** (F=11.7, ort. farkı
   −0.139p). Taban 1'deki yeni kaynaktan sıfırdan kurulmalı. Ayrıca karar
   **kanal başına** verilmeli: prim 0/34, çeyrek **6/34** uyuşmazlık.
3. **Kapı — 🤖 ama SAYAÇ DURDU.** 19/60 geçerli gün; ileriye dönük sıfır geçerli
   ölçüm üretiliyor. 1 çözülmeden kapı ilerlemez. Bu bir arıza değil, nöbetçinin
   doğru çalışması. DoD: 1 uygulandıktan sonra sayaç yeniden ilerliyor.

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
