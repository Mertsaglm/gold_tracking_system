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
| Dil / ortam | Python 3.12 · `src/` · **872 test** (2026-08-28) |
| Bağımlılık | requests, PyYAML, yfinance, pytrends, matplotlib (lazy) |
| Depolama | SQLite **12 tablo** + diff'lenebilir `data/altin.sql` + aylık CSV arşiv |
| Üretim | GitHub Actions — `archive.yml` (`*/15`), `daily.yml` (15:35 UTC) · **`test.yml`** (push/PR merge kapısı, 2026-08-28) |
| Bildirim | Telegram Bot API (saf `requests`) |
| Repo | **public** → Actions dakikası sınırsız; `.env` ve `ai/PROFILE.md` gitignore'da |

---

## 2. Mimari — veri nasıl akıyor

**İki üretim workflow'u, iki ritim** (+ `test.yml` — üretime dokunmayan merge
kapısı, 2026-08-28). Actions cron'u kısıtlıyor: `*/15` yazar, gerçekte çok daha
azını teslim eder. Bu platform kısıtı ücretsiz düzeltilemez; sağlık metrikleri
**gözlemlenen** ritme kalibre edildi (`archive_observed_freq_minutes: 90`),
nominale değil — yoksa sağlıklı sistem her gün "arıza" derdi.

⚠️ **Ritim çok oynak ve payda bayat:** ölçüldü 2026-08-28 — 08-25 ~30, 08-26 **24**,
ama 08-27/28 **yalnız 2 çalışma/gün**. Koşumlar başarısız değil, hiç tetiklenmiyor
(`gh run list` hepsini `success` gösterir). 90 dk'lık payda bu dalgalanmaya göre
yeniden kalibre edilmedi → metrik gerilemeleri gizleyebilir (açık iş).

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
  **birincil kol.** Kapı değişkeni: reel net mevduat faizi. Kademeler bilerek
  **dar** tutulmuştu (1.25× / 0.75×), çünkü ölçülen kenar t≈1.4 — en iyi aday ama
  kanıt değil. **2026-08-11: kademe KAPATILDI (ADR #012-A)** — kural örneklem-içi
  ölçümde bile başa başın altında kaldı (ort. %-0.64, başa baş 0.00). Hüküm artık
  daima `NORMAL AL` 1.00×; kol alım planına **hiç dokunmuyor**.
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
Kademe önce **kaldırılmadı** (Mert'in gerçek alım davranışını değiştirir → onun
kararı) ama hüküm bloğu her gün kendi kanıt durumunu beyan etmeye başladı.
**2026-08-11'de karar verildi ve kademe KAPATILDI** (ADR #012-A): kuralın ortalama
gram kazancı %-0.64 (başa baş 0.00'ın altında) ve canlı doğrulamada -%1.55 gram.
"Küçük ve simetrik" savı da düştü — üst kademe erişilemez, 30/30 alt kademe
ateşledi. Mekanizma silinmedi, kapıya bağlandı; açılma şartı N≥30 ve |t|≥2 ile
+1.99p. → Dersler **L-017**, **L-018**

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

### Kaynak denetimi — 2026-08-16 (ADR #013)

Mert sordu: *"üretilen tahminler sağlam bir şekilde mi üretiliyor?"* Prim
serisinde **2026-07-29'da kalıcı −1.25 puanlık basamak** bulundu. AGENTS.md §5
kuralı işledi: *"metrik mi değişti, sistem mi?"* → **metrik değişti.**

`yfinance` tek bir ticker (`GC=F`) için iki farklı seviye servis ediyordu:
canlı kotasyon **vadeli** kontrat, günlük bar geri-düzeltmeli. Ağustos kontratı
vadesini doldurunca canlı kotasyon **Aralık kontratına** (GCZ26, spot+%1.39)
atladı ve doğrudan `theoretical`'e girdi. Prim 17 gün boyunca sahte iskonto
gösterdi; `|prim|>%1.5` alarmı 08-11…08-14'te **4 kez boşuna** gitti.

Hüküm/backtest/grafik **etkilenmedi** — onlar günlük barı okuyor. Çözüm: ons →
Truncgil spot. Kirli 14 gün z tabanından düşüldü çünkü z **genişleyen pencere**:
bırakılsaydı tespit eşiği 0.25p yerine 1.22p olurdu (5× sağır) ve 2028'de bile
düzelmezdi. → Ders **L-019**. Test 851 → **855**.

### İki-rapor denetimi — 2026-08-28 (ADR #014)

25 Ağustos'ta iki bağımsız denetim raporu üretildi (Claude + GPT). Bu tur
onların **iddialarını doğrulama** turuydu: raporlar kanıt değil hipotez sayıldı,
her bulgu bugünkü kodda ve veride yeniden ölçüldü.

**İki rapor aynı olguyu ZIT okudu.** 08-17 sonrası prim varyansının çökmesini
GPT *"kaynak düzeltmesi çalışıyor, korunmalı"*, Claude *"metrik öldü"* diye
yorumladı. Ayırt eden ölçüm: **ons prim formülünde sadeleşiyor mu?**

```
market_has  = 0.995 × (ons_trunc/31.1 × usd_trunc)
theoretical =         ons_trunc/31.1 × usd_yfinance
prim        = 0.995 × usd_trunc/usd_yfinance − 1     ← ONS YOK
```

934 kayıtta doğrulandı: `usd_trunc/usd_yf` vekili 08-17 sonrası prim varyansının
**%99.81'ini** açıklıyor (düzeltme öncesi %18.2). Saf-Truncgil tabanında prim
her gün tam **−0.5000%**; 08-22'de gün-içi varyans **tam sıfır**. **Claude
haklı.** ADR #013 gerçek bir arızayı düzeltirken ölçümün **var olma şartını**
(iki bacağın bağımsızlığı) yok etmişti. → Ders **L-020**.

**Konsensüs aransaydı yanlış cevap çıkardı** — iki rapor da "düzeltme yerinde"
öncülünü paylaşıyordu. Ölçüt her zaman kendi ölçümündür.

Eklenen korumalar: **bağımsızlık nöbetçisi** (üretim verisinde her gün
`piyasa/teorik` oranının gün-içi CV'si; eşik altındaysa `indicative=1` +
`reason='turetilmis'`, kapı sayacı dışına), rejim **dejenerelik kapısı**, `notify`
**takvim + bayatlık** kapısı, GMA panelinin DB'den beslenmesi, panelin tek kez
hesaplanması, `daily_job` adım hatalarının rapora basılması ve **CI workflow'u**.

**Ölçülen bedel dürüstçe yazıldı:** geçerli gün **30 → 19**; kapı, bağımsız ons
kaynağı kararı verilene kadar ilerlemiyor. Sayaç ilerleseydi kapı bir **kimlik**
üzerinden açılırdı.

**Fixture de düzeltildi:** `gram_has_sell = teorik × 1.0045` üretiyordu — kimliğin
ta kendisi. 855 test yeşilken 8 gün boyunca kimse fark etmedi; adı tam bu iş için
konmuş `test_dejenere_metrik.py` bile sessizdi. Sentetik veri rejimsizse koruma
testleri **vacuous** geçer.

**Test:** 855 → **872**; 13 mutasyon, **13/13** yakalandı.

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
| "Ons'u gram ile aynı kaynağa taşımak prim'i onardı" (ADR #013) | **Onarmadı, ÖLDÜRDÜ** — ons prim formülünde cebirsel olarak sadeleşiyor; 08-17 sonrası prim'in **%99.81'i** yalnız iki USD beslemesinin oranı (öncesi %18.2). Prim ölçüm değil kimlik oldu (ADR #014, L-020) |
| "Rejim satırı 3 aylık getiri kenarı ölçüyor" | **Tabanın birebir kopyasıymış** — FRED ölü olduğu için sınıflandırıcı 2585/2585 güne aynı etiketi veriyor; `X` ≡ `_baseline`. 48/48 raporda "güven: orta" ile basılmış, bilgi değeri **tam sıfır** (ADR #014) |
| "17/17 provada iki z tabanı aynı kararı verdi" | **Yalnız PRİM kanalı için doğru** — çeyrek kanalında **6/34 uyuşmazlık** (ölçüldü 2026-08-28). Tek bir "taban" kararı iki farklı istatistiksel rejime dayatılıyordu |
| "853 test regresyon zırhı" | **GitHub'da hiç koşmuyormuş** — iki üretim workflow'unda da `pytest` yok; "son 200 koşum success" veri çekiminin patlamadığını gösteriyordu, testlerin geçtiğini değil (2026-08-28, `test.yml` eklendi) |
| "Panel fiyatı ile özet ons aynı şey" | **12/12 raporda ort. +1.2 puan farklıymış** — GMA paneli kendi ağ isteğiyle **kapanmamış** GC=F barını okuyordu, kirli fiyatı temiz kapanış ortalamalarıyla karşılaştırıyordu (ADR #014) |
| "Hafta sonu bildirimi yalnız hafta sonu gider" | **3 kez PAZARTESİ gitmiş** — bayat CSV satırında `all_fresh` takvimden değil dump'ın son satırının bayrağından okunuyordu; Telegram arşivinde 3/3 dakika hassasiyetinde eşleşti (ADR #014) |

---

## 5. Bugün bilinen sınırlar

0. 🔴 **PRİM BUGÜN ÖLÇÜM TAŞIMIYOR** (ADR #014, 2026-08-28) — **listedeki en
   pahalı sınır, çünkü aşağıdaki 3. maddeyi de geçersizleştiriyor.** Ons ile
   gram aynı satıcıdan (Truncgil) gelince ons prim formülünde cebirsel olarak
   sadeleşiyor; geriye satıcının kendi saflık çarpanı kalıyor. Ölçüldü: prim
   varyansının **%99.81'i** yalnız iki USD beslemesinin oranı. Bağımsızlık
   nöbetçisi bunu her gün tespit edip kayıtları kapı sayacı dışına alıyor ve
   raporun en üstüne kırmızı satır basıyor. **Kalıcı çözüm bağımsız bir spot ons
   kaynağı gerektiriyor — karar Mert'te** (`../../ai/STATE.md` → Sıradaki 3 İş → 1).
   Ders **L-020**: bir arızayı düzeltirken ölçümün var olma şartını yok etme.
1. **Karne ölçüm üretemiyor** — ve bu artık KABUL EDİLMİŞ bir sonuç (ADR #012-B,
   2026-08-11). Gölge kol **yapılmayacak**, gerekçe ölçüm: (a) taktik gölge kol
   %100 `TUT` kaydeder çünkü kapı açık olsa bile beklenen-kazanç üreticisi yok
   → sıfır bilgi; (b) çekirdek gölge kol gereksiz, kural deterministik ve tüm
   girdileri saklanıyor → karşı-olgu backtest ile TAM yeniden üretilebilir.
   **Genel kural:** gölge kol, karşı-olgu yeniden ÜRETİLEMEDİĞİNDE gerekir.
2. **Taktik kol SAT diyemez** — beklenen kazanç üreticisi yok ve ADR #007-H'ye
   göre dürüst bir aday da yok.
3. **Prim + çeyrek z-skoru kapalı — ve SAYAÇ DURDU** (2026-08-28). Kapı gün
   sayar, kayıt değil (gün içi örnekler birbirinin tekrarı). ⚠️ Eski tarih
   tahminleri (~09-14, sonra ~10-02) **GEÇERSİZ**: bağımsızlık nöbetçisi 08-17
   sonrası günleri `turetilmis` işaretlediği için geçerli gün **30 → 19** düştü
   ve ileriye dönük yeni geçerli gün üretilmiyor (bkz. madde 0). Kalan 19 günün
   tamamı eski yfinance rejiminden ve o rejim yenisiyle **aynı dağılım değil**
   (F=11.73, ortalama farkı −0.139p) → taban yeni kaynaktan **sıfırdan** kurulmalı.
   ⚠️ Taban kararı **kanal başına** verilmeli: kuru provada prim kanalında iki
   taban 0/34 uyuşmazlık, **çeyrek kanalında 6/34**. "17/17 iki taban aynı"
   iddiası yalnız prim için doğruydu.
4. **FRED ölü** (2026-07-07'den beri) → DXY yfinance `DX-Y.NYB` yedeğine düşüyor;
   reel faiz göstergesi **bilerek** kapalı (`^TNX` nominaldir, TIPS reel getirisi
   değil — nominali "reel" diye sunmak ölçümü sahtelemek olurdu).
   **Google Trends de 12/14 gün ölü** (pytrends 429) → panel fiilen **5/7**
   (ölçüldü 2026-07-29, son 14 rapor). Kör gösterge paydadan düşer, uydurulmaz.
   ⚠️ **FRED'in ikinci, gizli bedeli (ADR #014):** rejim sınıflandırıcısı reel
   faiz olmadan **tek sınıfa** çöküyordu (2585/2585 gün "X") ve "X rejimi" tüm
   verinin, yani tabanın kendisi oluyordu. Rapor bunu 48/48 gün "güven: orta"
   ile bir rejim ÖLÇÜMÜ gibi bastı; `_baseline` satırıyla birebir aynıydı.
   Artık dejenerelik tespit ediliyor ve sinyal "ölçemedim" diyor.
   ⚠️ Panel paydası hâlâ **cevap veren gösterge sayısı** → uzlaşı skoru günler
   arası doğrudan kıyaslanamaz. Sabit paydaya geçmek etiket tanımını değiştirir,
   ayrı karar.
5. **TÜFE serisi bayat** (`TP.FE.OKTG01` son değer 2025-12-01) — `evds_job.context`
   sessizce `enf_bek_12ay`'a düşüyor. `ozellikler.feature_vector` bilerek DÜŞMEZ.
6. **Çeyrek priminde sezon düzeltmesi yok** — yıllar süren arşiv ister; düz z
   sezonu "anomali" sanabilir. Sınır gizlenmiyor, rapora yazılıyor.
7. **Grafiğin ölçülmüş yön kenarı YOK** (2026-07-29 tazelendi). Faz artefaktı
   düzeltildi (ADR #010-A) → 54 karşılaştırmada tek "zayıf kanıt" satırı kaldı
   (`RSI aşırı satım · 1ay · +2.0p`, N=16, in-sample ve OOS ikisi de yetersiz).
   Bonferroni'den sonra bu kanıt değildir. Grafik bölümü **planlama geometrisi**;
   hüküm üretmez, üretmemesi de bir hata değil ÖLÇÜM SONUCUdur.
8. ✅ **Açık kolun kademesi KAPATILDI** (ADR #012-A, 2026-08-11). `reel_mevduat > %10`
   kuralı ateşlendiğinde ertelemenin ortalama gram kazancı **%-0.64** (N=22, t=1.03)
   — başa baş **0.00**'ın ALTINDA, yani örneklem-**içi** ölçümde bile kayıp. Canlı
   örneklem-dışı doğrulama: **-%1.55 gram**. "Küçük ve simetrik" savı da düştü: üst
   kademe erişilemez, canlıda 30/30 alt kademe ateşledi. Hüküm artık daima
   `NORMAL AL` 1.00×. Mekanizma silinmedi, kapıya bağlandı; açılma şartı kayıtlı
   (**N≥30 ve |t|≥2 ile +1.99p**). **Sistem artık iki kolda da ölçemediği hiçbir
   şeye göre davranmıyor.**
9. **Telegram komutları üretimde ölü — KABUL EDİLDİ** (ADR #012-E). Actions
   push-only; `/hukum` `/karne` `/grafik` yalnız yerelde `src.telegram_bot` açıkken
   yanıt verir. Ölçüldü: 4 ayda 3 komut, 0 cevap. Komutların döndüğü her şey zaten
   günlük push raporunda; polling eklemek onu kritik arşiv yoluna sokardı.
10. **Bildirim hattı 13 gün sessizce ölüydü** (2026-07-29 → 08-10, ADR #011,
   L-018) — kaçırılmamış `<` yüzünden Telegram 400 döndürüyordu ve
   `continue-on-error: true` 125 koşuyu yeşil bırakıyordu. Onarıldı (kaçış +
   izolasyon + damga geri alma + rapora arıza satırı) ve üretimde doğrulandı
   ("2 tetik, 2 gönderildi, 0 HATA"). **Ders: teslim yolu, karar mantığı kadar
   test edilmelidir.**
11. **Testler sözleşmeyi korur, DOĞRULUĞU değil.** Test paketi bir formülün sessizce
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
5. Kararların gerekçesi `../../ai/DECISIONS.md` (#001…**#014**). Tuzaklar
   `LESSONS.md` (**L-001…L-020**) — numara uzayı kökle **ortak**, bkz. `DECISIONS.md` #003.
6. Testler: `.venv/bin/python -m pytest -q` → **872 test**, tamamı geçmeli (~10 sn, ağa
   çıkmaz, gerçek DB'ye dokunmaz). Kırmızı bir test neredeyse daima haklıdır:
   çoğu bir ADR'yi ya da dersi kilitliyor ve gerekçesi docstring'inde yazılı.
   Testi susturmak, korumayı sessizce kaldırmakla aynı şeydir.

**Bir şeyi değiştirmeden önce üç soru:** "Bu sayının farklı çıkabilmesi için ne
olması gerekir?" (L-010) · "Bu korumayı atlayan bir yol var mı?" (L-011) ·
"Korumanın kapsamı dışında hangi fiil/alan kaldı?" (L-014).
Bu üç soru bu projede en pahalı hataları yakaladı.

**Bir koruma eklersen** onu düşüren testi de yaz ve **düştüğünü kanıtla**:
korumayı bilerek boz, testi koş, geri al (L-015 · `AGENTS.md` §5).
