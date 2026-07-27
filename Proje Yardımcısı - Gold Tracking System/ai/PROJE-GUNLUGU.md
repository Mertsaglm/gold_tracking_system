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

**Son güncelleme:** 2026-07-27 · **Üretimdeki son commit:** `1d983ad`

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
| Dil / ortam | Python 3.12 · **7.805 satır** `src/` · **299 test** |
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

---

## 5. Bugün bilinen sınırlar

1. **Karne ölçüm üretemiyor.** Sistem bunu artık **söylüyor** ("ÖLÇÜM
   İÇERMİYOR") ama döngü **kırılmadı**. Kırmak için gölge kol gerekiyor;
   karar ~Ekim 2026'ya bırakıldı (ADR #008-B).
2. **Taktik kol SAT diyemez** — beklenen kazanç üreticisi yok ve ADR #007-H'ye
   göre dürüst bir aday da yok.
3. **Prim + çeyrek z-skoru kapalı** — 60 **gün** kapısı ~2026-09-12'de açılacak.
   Kapı gün sayar, kayıt değil (gün içi ~10 örnek birbirinin tekrarı).
4. **FRED ölü** (2026-07-07'den beri) → DXY yfinance `DX-Y.NYB` yedeğine düşüyor;
   reel faiz göstergesi **bilerek** kapalı (`^TNX` nominaldir, TIPS reel getirisi
   değil — nominali "reel" diye sunmak ölçümü sahtelemek olurdu). Panel 6/7.
5. **TÜFE serisi bayat** (`TP.FE.OKTG01` son değer 2025-12-01) — `evds_job.context`
   sessizce `enf_bek_12ay`'a düşüyor. `ozellikler.feature_vector` bilerek DÜŞMEZ.
6. **Çeyrek priminde sezon düzeltmesi yok** — yıllar süren arşiv ister; düz z
   sezonu "anomali" sanabilir. Sınır gizlenmiyor, rapora yazılıyor.
7. **`chart.measure_edge` faz artefaktı** — taban tek fazdan ölçülüyor; h≥63'te
   faz gürültüsü eşiğin 3-11 katı. Düzeltme hazır (`gram.phase_matched_baseline`),
   `chart.py`'ye taşınmadı.
8. **`deploy/altin-backup.service` var olmayan `scripts/backup.sh`'ı çağırıyor** —
   Oracle senaryosu aktive edilirse bu timer patlar.

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
5. Kararların gerekçesi `../../ai/DECISIONS.md` (#001…#008). Tuzaklar
   `LESSONS.md` (L-001…L-012) — numara uzayı kökle **ortak**, bkz. `DECISIONS.md` #003.
6. Testler: `.venv/bin/python -m pytest -q` → **299** geçmeli.

**Bir şeyi değiştirmeden önce sor:** "Bu sayının farklı çıkabilmesi için ne
olması gerekir?" (L-010) ve "Bu korumayı atlayan bir yol var mı?" (L-011).
Bu iki soru bu projede en pahalı iki hatayı yakaladı.
