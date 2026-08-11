# PROJE GÜNLÜĞÜ — Altın Takip Sistemi

> **Bu dosya ne?** Projenin **kararlı** kaydı: ne inşa edildi, ne ölçüldü, hangi
> iddia çürüdü, bugün sistemin sınırları ne. Geçmiş değişmez — bu yüzden devir
> paketinde durur ve nadiren güncellenir.
>
> **Bu dosya ne DEĞİL?** Canlı durum. "Nerede kaldık, sırada ne var, ne zaman ne
> yapılacak" sorularının cevabı **daima `../../ai/STATE.md`**'dedir (TAKVİM
> tablosu + 👤 SENDE KALANLAR orada). İki yere yazılan şey ayrışır.
>
> **İnşa dönemi (Faz 1-7) kanıt kaydı:** `../../docs/TESLIMAT-ARSIV.md` (314 satır,
> ölçüm ölçüm). Bu dosya oradan devralır ve **Faz 8 + denetim** dönemini anlatır.

**Son güncelleme:** 2026-07-27 (2. tur: regresyon zırhı) · **Üretimdeki son
commit:** `571646c` + bu turun değişiklikleri

---

## 1. Proje bir bakışta

Mert'in **elindeki gram sayısını artırmasına** yardım eden kişisel karar-destek
sistemi. GitHub Actions üstünde 7/24 kendi kendine çalışır; kullanıcının hiçbir
şey çalıştırması gerekmez.

**Amaç fonksiyonu: terminal GRAM sayısı** — TL getirisi değil. Bu seçim projenin
belkemiği: ölçüt gram olunca TL enflasyonu artefaktı kendiliğinden ölür ve her
iddia yanlışlanabilir olur. "100 gramla başladın, 108 gram bitirdin → tuttu."

| | |
|---|---|
| Dil / ortam | Python 3.12 · **7.915 satır** `src/` · **800+ test** (8.138 satır) |
| Bağımlılık | requests, PyYAML, yfinance, pytrends, matplotlib (lazy) |
| Depolama | SQLite **12 tablo** + diff'lenebilir `data/altin.sql` + aylık CSV arşiv |
| Üretim | GitHub Actions — `archive.yml` (`*/15`), `daily.yml` (15:35 UTC) |
| Bildirim | Telegram Bot API (saf `requests`) |
| Repo | **public** → Actions dakikası sınırsız; `.env` ve `ai/PROFILE.md` gitignore'da |

---

## 2. Mimari — veri nasıl akıyor

**İki workflow, iki ritim.** Actions cron'u kısıtlıyor: `*/15` yazar, gerçekte
**~13 çalışma/gün** teslim eder. Bu platform kısıtı ücretsiz düzeltilemez;
sağlık metrikleri **gözlemlenen** ritme kalibre edildi (`archive_observed_freq_minutes: 90`),
nominale değil — yoksa sağlıklı sistem her gün "arıza" derdi.

```
archive.yml  (*/15)
  archive_fetch  → truncgil + yfinance → data/archive/YYYY-MM.csv   (kaynak boşsa retry)
  restore_db     → data/altin.sql'den SQLite kur (salt-okunur bağlam)
  notify         → eşik değerlendir → soğuma/tavan → Telegram
  commit + push  (concurrency: repo-commit)

daily.yml  (15:35 UTC = 18:35 TR)
  restore_db
  daily_job:
    1  import_actions   CSV arşivi → DB
    2  evds_job         TCMB EVDS günlük
    3  ohlc_hist        yfinance günlük OHLC → ohlc_daily
    3b history          ons×kur → history_daily   (ATR'nin kaynağı)
    3c signals          z-skor KURU PROVASI → data/zskor_prova.jsonl
    3d tahmin           hüküm kaydet → giriş doldur → vadesi geleni çöz
    4  reconcile        (yalnız pazartesi) hafta sonu mutabakatı
    5  report           markdown + Telegram   (pazar: haftalık)
    6  grafik_ciz       4 panel PNG → Telegram
  dbdump → commit + push
```

**Neden dump?** Binary SQLite git geçmişini şişirir. Bunun yerine deterministik
(mantıksal anahtara göre sıralı) SQL metin dump'ı commit'lenir → günlük diff =
yalnız yeni satırlar. Actions **stateless** çalışır: DB her koşuda dump'tan
kurulur, iş biter, dump yeniden yazılır. Bu yüzden **bir tablo dump'a girmiyorsa
her gün sıfırlanır** — `predictions` üçlüsü tam bu yüzden `dbdump._TABLES`'ta.

**Kritik zincir (en pahalı sessiz arıza nerede?)**

| Zincir | Arıza şekli |
|---|---|
| `archive → notify` | Yanlış eşikle alarm, ya da alarmın hiç ateşlenmemesi |
| `daily → karar/karne` | **Yanlış HÜKÜM + karnenin yanlış ölçmesi** ← en pahalısı |

---

## 3. Yolculuk

### Faz 1-7 — inşa dönemi (2026-07-07 → 07-25)

Kanıt kaydı `../../docs/TESLIMAT-ARSIV.md`'de. Kısaca: veri katmanı, tarihsel
backtest, sinyal motoru, tam otonomluk (Actions + Telegram), grafik yorumu,
çoklu-IDE Usta sistemi. Bu dönemin en önemli özelliği **ölçüp geri çekmek**:
rejim üstünlükleri, prim-koşullu DCA ve destek/direnç seviyelerinin yön kenarı
— üçü de ölçüldü ve **çürütüldü**, rapor dili buna göre değiştirildi.

### Faz 8 — karar motoru (2026-07-26, ADR #007)

**Tetikleyen:** Mert'in "bu proje benim hiç işimi görmez, net tahmin söylemesi
lazım" + "her ay düzenli alıyorum, **elimdeki gramı artırmalıyım**" cümlesi.
Sorun hedge dili değildi — **karnesizlikti.**

**En riskli varsayım ÖNCE ölçüldü ve DÜŞTÜ.** "Trade ederek gram artırılabilir"
varsayımı, kod yazılmadan, 2561 gün (2016-01-04 → 2026-07-24) üzerinde,
örtüşmeyen pencerelerde, **tüm fazlarda**, mevduat carry'si net dahil ölçüldü:

| Ufuk | N (bağımsız) | SAT gram kazancı (ort) | SAT kazanır | En kötü tek pencere |
|---|---:|---:|---:|---:|
| 1 hafta (5g) | 512 | **−0.47%** | %42 | −24.0% |
| 1 ay (21g) | 121 | **−1.99%** | %36 | **−36.2%** |
| 3 ay (63g) | 40 | **−6.14%** | %22 | −49.4% |

Alt dönemler: 2016-19 −1.35% · 2020-22 −2.84% · 2023-26 −1.98% → **her rejimde
aynı işaret, yapısal** (TL mevduat faizi ≈ TL değer kaybı ≈ gram TL sürüklenmesi).

Gidiş-dönüş maliyeti: `banka_hesap` **%1.20** · `altins1` **%0.40** · `fiziki` **%3.00**.
→ Bir SAT sinyalinin 1 ay ufkunda tabanı **+3.18 puan** yenmesi gerekiyor.

**Sonuç: satmak ortalamada gram KAYBETTİRİR.** Sistem buna göre iki kola ayrıldı:

- **ÇEKİRDEK** — aylık düzenli alımı zamanlar. Makas ödemez → eşiği daima düşük →
  **birincil kol, açık.** Kapı değişkeni: reel net mevduat faizi. Kademeler
  bilerek **dar** (1.25× / 0.75×), çünkü ölçülen kenar t≈1.4 — en iyi aday ama
  kanıt değil. Kol alımı **asla kesmez**.
- **TAKTİK** — sat/geri al. ~%1.20 makas öder → **doğuştan KAPALI**
  (`karar.taktik.aktif: false`). Açılma şartı önceden config'e yazıldı ve
  gevşetilmez.

**Alt fazlar:**

| Faz | Ne geldi |
|---|---|
| A+B | `gram.py` (gram hakemi, faz-düzeltmeli taban) · `karar.py` (iki kol + sert kapı) · rapor başına HÜKÜM · `/hukum` |
| C | `tahmin.py` — hüküm kaydı **değiştirilemez** (`trg_predictions_immutable`), giriş AYRI tabloda (look-ahead önlemi), çözüm gram uzayında · `/karne` |
| D | `ozellikler.py` — **tek özellik giriş noktası**; canlı ve replay aynı fonksiyonu çağırır → look-ahead yapısal olarak imkânsız. EVDS **yayın gecikmesi** bir kontaminasyonu kapattı (reel net mevduat %12.7 → %13.1) |
| E | `tahmin_backfill.py` — 458 haftalık asof, **14 aday**, en iyisi +1.4p (t≈1.4). **Hiçbiri +3.18p'yi geçemedi.** Örneklem-İÇİ ölçüm olduğu için bu bir **ÜST SINIR**: içeride aşılamayan eşik dışarıda hiç aşılmaz |
| F, G | Kod işi değil — F ~Ekim'de karneye bakılıp verilecek karar; G (MTF) **askıda**, çünkü E hiçbir aday bulamadı |
| H | `grafik_ciz.py` — 4 panel PNG, `send_photo`. matplotlib **lazy import**: yoksa sessizce atlanır (`archive.yml` kurmuyor) |

**Ağırlık öğrenme REDDEDİLDİ (ADR #007-D):** 1 ay ufkunda ~5 bağımsız makro
epizot var; 7 bileşen × 3 ufuk = 21 ağırlığı "kayıt biriktikçe yeniden kestirmek"
ders kitabı aşırı-uydurmadır. Yerine tek kapı değişkeni + sabit önceden-kayıtlı
eşikler; diğer göstergeler **bağlam olarak gösterilir, OY VERMEZ**.

### Denetim — 2026-07-27 (ADR #008)

Karar motoru **push edilmeden önce** uçtan uca denetlendi. İyi ki: 26 bulgunun
en büyüğü sistemin dürüstlük iddiasının merkezindeydi.

**🔴 Karne hiçbir şey ölçmüyordu.** `gram.hukum_dogru_mu` `SAT*` olmayan her
hükme tabanla (`TUT`) aynı cevabı veriyor. Sistem ise yalnız `AL_*` (çekirdek) ve
`TUT` (taktik, kapı kapalı) üretebiliyordu. Sonuç: "tabana fark" ve "gram etkisi"
**piyasa ne yaparsa yapsın 0.00** (11 senaryoda doğrulandı). Dahası kapı, açılma
şartı olarak tam bu iki sayıyı okuyordu → **kapalı kapı → TUT → sıfır skor →
kapalı kapı.** Ekim'de yazılacak "trade kolu kalıcı kapalı" ADR'si bir ölçüme
değil, bir **totolojiye** dayanacaktı — ve tablo gerçek ölçümden ayırt
edilemediği için fark edilmeyecekti. → Ders **L-010**.

**🟠 `asof = T−1` garantisi kâğıt üstündeydi.** Koruma yazılmıştı ama parametre
opsiyoneldi ve **hiçbir çağıran geçmiyordu**; ayrıca korumasız ikinci bir kopya
vardı. Ölçüldü: kesişimin her iki bacağı da hafta içi aynı-gün satırını
içeriyordu → ilk hafta içi koşumda bugünün **yarım barı** `asof` olacak ve
`predictions`'a değiştirilemez yazılacaktı. → Ders **L-011**.

**🟠 `beklenen_gram_kazanc_pct` üreticisi YOK.** `taktik_hukum` bu alanı okuyor,
`gram.engel_ozet` hiç üretmiyor → SAT dalı üretim verisiyle **erişilemez**. Bu
bir unutma değil ölçüm sonucu (ADR #007-H: 14 aday, hiçbiri geçmedi) — bu yüzden
**uydurma tahminci konulmadı**, kod artık "ÜRETİCİSİ BAĞLI DEĞİL" diyor ve bunu
"hesaplanamadı"dan ayırıyor.

**🟡 Diğerleri:** `daily_job` altı adımı da yutup daima 0 ile çıkıyordu → Actions
günlerce yeşil kalabilirdi · "günlük hareket" alarmı rapordan sonra fiyatı
kendisiyle karşılaştırıyordu · hayalet hafta sonu barları kalıcı yazılıyordu ·
test fixture'ı üreticinin hiç yazmadığı alanı doğruluyordu (**L-012**) ·
7 ölü config anahtarı · README ağacı karar motorunun tamamını atlıyordu.

**Denetimin kendisi de denetlendi** ve 3 eksik çıktı — ikisi ilk düzeltmenin
kendi hatasıydı: `history_daily`'ye bugünün satırı hâlâ yazılıyordu (tabloyu
16 yer okuyor → **kaynak** kapatıldı), verilen L numarası devir paketiyle
çakışıyordu, kökte L-005…L-008 hiç yoktu. Ortak kalıp: **yama tüketiciye değil
kaynağa konmalıydı** (L-011).

### Regresyon zırhı — 2026-07-27, 2. tur (ADR #009)

**Tetikleyen:** *"Yakın zamanda Claude Code aboneliğim bitecek; ileride düşük
modelli yapay zekalar projemi bozmasın."* Bu, ADR #001/#002'nin doğal sonucu:
kurallar taşınabilir hâle getirilmişti, **ama uygulandığını hiçbir şey
doğrulamıyordu.** Mevcut 299 test doğruydu; ne var ki bu projede yaşanan en
pahalı arızaların hiçbiri birim seviyesinde değildi (donuk tablo, bağlanmamış
koruma, yutulan hata, totolojik metrik — hepsi PARÇALAR ARASI).

**Ne yapıldı:** 491 yeni test, 16 dosya → **804 test**. Ağırlık merkezi birim
değil **sözleşme**: uçtan uca `daily_job` koşumu (izole kök, ağ kapalı) ·
config/şema/workflow/gizlilik sözleşmeleri · yapısal korumalar (AST ile "bu
korumayı atlayan yol var mı?") · ağ izolasyonu (soket kapalı) · dejenere metrik
avı (L-010) · doküman-kod tutarlılığı · saf çekirdeğin matematiksel değişmezleri
(ölçek/kaydırma bağımsızlığı).

**Testin kendisi ölçüldü.** "Yazdım, geçiyor" bu projede kabul edilebilir bir
cümle değil (L-012). **20 kontrollü mutasyon** uygulandı — `asof` filtresini
gevşet, hafta sonu filtresini sil, kapıyı config'ten aç, dump'tan tablo düşür,
imza sırasını değiştir, eşiği koda göm, karar katmanına ağ ekle... — her biri
`try/finally` ile geri alındı. **20/20 yakalandı.** → Ders **L-015**.

**Zırh 4 gerçek açık buldu ve kapattı:**

| Açık | Ölçüm | Düzeltme |
|---|---|---|
| `ticks` her koşumda yeniden yazılıyor | dump'ta 15 999 satır, **tekil 1 663** (9.6×); en eski satır 23 kopya | benzersiz indeks + `INSERT OR IGNORE`; mevcut DB'leri **önce onarıp sonra** indeksleyen migration → **L-013** |
| Tahmin kaydı **silinebiliyordu** | trigger yalnız UPDATE'i engelliyordu | `BEFORE DELETE` trigger'ı → **L-014** |
| `kaynak`/`model_version` korumasız | kaydın hangi karneye sayıldığını bu iki kolon belirliyor | trigger listesine eklendi; trigger'lar artık `DROP+CREATE` |
| `deploy/altin-backup.service` → olmayan script | STATE backlog'unda duruyordu | `scripts/backup.sh` yazıldı; git/ağ/silme YOK (L-007) |

**Veri sonucu:** `data/altin.sql` **33 699 → 19 369 satır** (4.98 → 2.8 MB).
Tekilleştirme commit'li dump'ın kendisinden yapıldı, bayat yerel sqlite'tan
değil (L-009); kopyalar birebir aynıydı → bilgi kaybı sıfır; `restore→dump`
sabit noktası bayt bayt doğrulandı. Geriye uyum korundu: eski commit'lerin
düz-`INSERT`'li dump'ları hâlâ yükleniyor.

---

### Ölçüm denetimi — 2026-07-29 (ADR #010)

**Tetikleyen:** *"Projede ne dönüyor, sonuçlar ne, pek anlamıyorum... en
önemsediğim şey grafik analizine göre tahmin yürütülmesi, bunun kontrolünü
yap."* Denetim iki ölçüm hatası buldu ve ikisi de aynı kökten geliyordu:
**eşik, ölçümün kendi gürültüsünden küçüktü.**

**1) Grafik ölçümü faz artefaktından arındırıldı.** ADR #007-E'de tespit edilip
Backlog'da bekleyen düzeltme koda taşındı: taban artık **tüm fazlardan**
ölçülüyor ve `esik = max(config_esik, faz_yayilimi)`. Ölçülen yayılım 1ay 1.0p ·
3ay 4.1p · 6ay 7.4p iken config eşiği 1.0p'ydi — yani 3-6 ay ufkundaki her
bulgu gürültünün 4-7 kat altında bir eşikle "kanıt" sayılıyordu.
Sonuç: **"zayıf kanıt" satırı 10 → 1**, "kenar yok" 14 → 23.
Ayakta kalan tek satır `RSI aşırı satım · 1ay · +2.0p` (N=16); 54
karşılaştırmada 1 zayıf satır Bonferroni'den sonra kanıt değildir.
**Hüküm: grafiğin ölçülmüş yön kenarı yok.** Rapordaki temkinli dil zaten
buna göreydi — artık ölçüm de dili doğruluyor.

**2) AÇIK olan kol kendi eşiğine göre hiç denetlenmemişti.** Aday taraması
yalnız **taktik** (kapalı) kolun eşiğine göre hüküm veriyordu. Üretimde her gün
hüküm üreten kol ise **çekirdek** ve eşiği daha düşük (makas ödemez).
Çekirdek eşiği eklenince: kademeyi üreten `reel_mevduat > %10` kuralı **+1.34p**,
başa baş **+1.99p**, t=1.03 → **eşiğin altında**. Yani sistemin "AZ AL 0.75×"
hükmü ölçülmüş bir kenara değil, en iyi adaya dayanıyor.
Kademe **kaldırılmadı** (Mert'in gerçek alım davranışını değiştirir → onun
kararı), ama hüküm bloğu artık her gün kendi kanıt durumunu beyan ediyor ve
veriyi `data/aday_taramasi.json`'dan okuyor — tarama tazelenince satır kendini
günceller. → Ders **L-017**

**Mutasyon disiplini kendi sınırını gösterdi.** 8 mutasyon uygulandı, **7'si**
yakalandı; `cekirdek_gecti` bayrağını sabit `False` yapan mutasyon **kaçtı**.
Sebep testin verisiydi: düz üstel sentetik seride her adayın tabana farkı özdeş
0.00 çıkıyor, bayrak hiç `True` olmuyor, test vacuous geçiyordu. İki rejimli
sentetik seri + "kurgu tetikleyici üretmediyse testi düşür" assert'i eklendi;
sonra 8/8 yakalandı. → Ders **L-016**, `AGENTS.md §5`'e 3. madde olarak yazıldı.

**Yan bulgu:** `telegram_chat.json` incelendi — Mert'in gönderdiği 3 komutun
(`/swing` ×2, `/grafik`) hiçbirine cevap yok. Sebep arıza değil mimari:
Actions push-only, komutlar long-polling ister. README bunu yazıyordu,
`PROJECT.md` yazmıyordu; düzeltildi.

**Test:** 797 → **815**.

---

## 4. Ölçülmüş ve ÇÜRÜTÜLMÜŞ iddialar (projenin ahlakı)

Bu projede bir iddia ham tabana karşı ölçülür; çıkmazsa **geri çekilir ve
saklanmaz**. Bugüne kadar düşenler:

| İddia | Sonuç |
|---|---|
| Rejim üstünlükleri (Faz 2) | Taban çizgisi + örtüşmeyen pencere düzeltilince **çöktü** |
| Prim-koşullu DCA | Adalet düzeltmesiyle **çöktü** |
| Destek/direnç seviyelerinin yön kenarı | **Yok** — kademe/stop planlaması için sunuluyor, yön iddiası olarak değil |
| Google Trends kontrarian | **Doğrulanmadı** |
| "Trade ederek gram artırılabilir" | **Düştü** — ayda −1.99%, her rejimde aynı işaret |
| 14 aday sinyalden biri eşiği geçer | **Hiçbiri geçmedi** (örneklem-içi üst sınır) |
| "Sıfır aralıklı Pazar barı ATR'yi aşağı çeker" (4 AI'ın ortak görüşü) | **Yön yanlış** — ATR %7.17 **yukarı**; kirleten Cumartesi barı |
| "Karne sistemin sicilini tutuyor" | **Tutmuyordu** — yapısal 0.00 (L-010) |
| "Tahmin kaydı değiştirilemez" | **Yarısı doğruydu** — UPDATE kapalı, DELETE açıktı (L-014) |
| "Ham tick sayısı veri hacmini ölçer" | **Ölçmüyordu** — koşum sayısını ölçüyordu, 9.6× şişkin (L-013) |
| "Kaynak-retry geçersiz kayıt oranını düşürür" | **Düştü** — %6.93 → %6.67 (2026-07-29). Geçersiz kayıtların **20/20'sinde** truncgil'in 8 alanı BİRDEN boş: kesinti 3×4 sn retry'dan uzun |
| "Grafikte 10 'zayıf kanıt' bulgusu var" | **9'u faz artefaktıydı** — taban tüm fazlardan ölçülünce 10 → 1 (ADR #010-A). Faz yayılımı 3ay'da 4.1p, eşik 1.0p'ydi |
| "Aday taraması eşikleri denetliyor" | **Yalnız KAPALI kolu denetliyordu** — açık kolun (çekirdek) eşiği hiç raporlanmıyordu; ölçülünce kolun kendi kuralı eşiğin ALTINDA çıktı (ADR #010-B, L-017) |

---

## 5. Bugün bilinen sınırlar

1. **Karne ölçüm üretemiyor.** Sistem bunu artık **söylüyor** ("ÖLÇÜM
   İÇERMİYOR") ama döngü **kırılmadı**. Kırmak için gölge kol gerekiyor;
   karar ~Ekim 2026'ya bırakıldı (ADR #008-B).
2. **Taktik kol SAT diyemez** — beklenen kazanç üreticisi yok ve ADR #007-H'ye
   göre dürüst bir aday da yok.
3. **Prim + çeyrek z-skoru kapalı** — 60 **gün** kapısı ~2026-09-14'te açılacak
   (19/60 @ 07-28, hız 0.86 gün/gün). Kapı gün sayar, kayıt değil (gün içi ~10
   örnek birbirinin tekrarı).
4. **FRED ölü** (2026-07-07'den beri) → DXY yfinance `DX-Y.NYB` yedeğine düşüyor;
   reel faiz göstergesi **bilerek** kapalı (`^TNX` nominaldir, TIPS reel getirisi
   değil — nominali "reel" diye sunmak ölçümü sahtelemek olurdu).
   **Google Trends de 12/14 gün ölü** (pytrends 429) → panel fiilen **5/7**
   (ölçüldü 2026-07-29, son 14 rapor). Kör gösterge paydadan düşer, uydurulmaz.
5. **TÜFE serisi bayat** (`TP.FE.OKTG01` son değer 2025-12-01) — `evds_job.context`
   sessizce `enf_bek_12ay`'a düşüyor. `ozellikler.feature_vector` bilerek DÜŞMEZ.
6. **Çeyrek priminde sezon düzeltmesi yok** — yıllar süren arşiv ister; düz z
   sezonu "anomali" sanabilir. Sınır gizlenmiyor, rapora yazılıyor.
7. **Grafiğin ölçülmüş yön kenarı YOK** (2026-07-29 tazelendi). Faz artefaktı
   düzeltildi (ADR #010-A) → 54 karşılaştırmada tek "zayıf kanıt" satırı kaldı
   (`RSI aşırı satım · 1ay · +2.0p`, N=16, in-sample ve OOS ikisi de yetersiz).
   Bonferroni'den sonra bu kanıt değildir. Grafik bölümü **planlama geometrisi**;
   hüküm üretmez, üretmemesi de bir hata değil ÖLÇÜM SONUCUdur.
8. **Açık kolun kuralı kendi eşiğini geçemiyor** (ADR #010-B). Çekirdek kademesini
   üreten `reel_mevduat > %10` +1.34p, başa baş +1.99p, t=1.03. Rapor bunu her gün
   beyan ediyor; kademeyi kaldırma/koruma kararı 👤 Mert'te (STATE TAKVİM).
9. **Telegram komutları üretimde ölü.** Actions push-only; `/hukum` `/karne`
   `/grafik` yalnız yerelde `src.telegram_bot` açıkken yanıt verir. Ölçüldü:
   `telegram_chat.json`'da 3 komut, 0 cevap.
10. **Testler sözleşmeyi korur, DOĞRULUĞU değil.** Test paketi bir formülün sessizce
   değiştirilmesini engeller; o formülün finansal olarak doğru olup olmadığını
   hâlâ ölçüm söyler (ADR #007-B/H). Zırhı "sistem doğru çalışıyor" diye okuma.

---

## 6. Sırada ne var?

**Buraya yazılmaz** — ikizlenir ve ayrışır. Tek kaynak:
**`../../ai/STATE.md` → 📅 TAKVİM & 👤 SENDE KALANLAR.**

O tabloda `Kim=👤` olan satırlar **yalnız Mert'in yapabileceği** işlerdir
(karar, onay, dışarıdan doğrulama). `AGENTS.md §2` gereği Usta, tarihi gelmiş
👤 satırlarını **her oturum başında sormak zorundadır**.

---

## 7. Devralan için — ilk 30 dakika

1. `../../ai/PROJECT.md` (kimlik) → `../../ai/STATE.md` (nerede kaldık + TAKVİM)
2. `/durum` yaz. Usta STATE'i okuyup özetliyorsa sistem devrede
   (dosyaların yerinde durduğunu görmek yeterli değil — **L-004**).
3. `git fetch` + `git rev-list --left-right --count origin/main...HEAD` →
   yerel checkout üretimin gerisindedir, **daima** (L-001).
4. Yerelde DB'ye dokunacaksan **önce** `python -m src.restore_db`. Yerelde
   `python -m src.dbdump` **çalıştırma** — bayat sqlite'tan dump almak 1.5 günlük
   üretim verisini siler (L-009).
5. Kararların gerekçesi `../../ai/DECISIONS.md` (#001…#010). Tuzaklar
   `LESSONS.md` (L-001…L-017) — numara uzayı kökle **ortak**, bkz. `DECISIONS.md` #003.
6. Testler: `.venv/bin/python -m pytest -q` → tamamı geçmeli (~5 sn, ağa
   çıkmaz, gerçek DB'ye dokunmaz). Kırmızı bir test neredeyse daima haklıdır:
   çoğu bir ADR'yi ya da dersi kilitliyor ve gerekçesi docstring'inde yazılı.
   Testi susturmak, korumayı sessizce kaldırmakla aynı şeydir.

**Bir şeyi değiştirmeden önce üç soru:** "Bu sayının farklı çıkabilmesi için ne
olması gerekir?" (L-010) · "Bu korumayı atlayan bir yol var mı?" (L-011) ·
"Korumanın kapsamı dışında hangi fiil/alan kaldı?" (L-014).
Bu üç soru bu projede en pahalı hataları yakaladı.

**Bir koruma eklersen** onu düşüren testi de yaz ve **düştüğünü kanıtla**:
korumayı bilerek boz, testi koş, geri al (L-015 · `AGENTS.md` §5).
