# DECISIONS.md — Karar Günlüğü (ADR)

> Yalnızca ÖNEMLİ kararlar: mimari, araç, yaklaşım seçimleri.
> Her karar "neden"i ve "tekrar gözden geçirme koşulu" ile kaydedilir.
> En yeni karar en üste.

---

## #013 — 2026-08-16 — Ons kaynağı SPOT'a taşındı; vadeli kontrat roll'ünün kirlettiği 14 gün z tabanından düşüldü

**Tetikleyen:** Mert: *"üretilen tahminler sağlam bir şekilde mi üretiliyor…"* Derin
denetimde prim serisinde **2026-07-29'da kalıcı −1.25 puanlık basamak** bulundu.
AGENTS.md §5 kuralı uygulandı: *"metrik mi değişti, sistem mi?"* → **metrik değişti.**

### Teşhis — kaynak sessizce enstrüman değiştirdi

`yfinance` tek bir ticker (`GC=F`) için iki farklı seviye servis ediyor ve sistem
ikisini birden kullanıyordu:

| Yol | Ne döner | Kim kullanıyordu |
|---|---|---|
| `fast_info.last_price` | **o anki VADELİ kontrat** | `prim_history` → prim, z-skor, alarmlar |
| `.history()` günlük bar | geri-düzeltmeli (≈spot) | `history_daily` → hüküm, backtest, grafik |

2026-07-29'da Ağustos kontratı vadesini doldurdu, canlı kotasyon **Aralık'a
(GCZ26)** atladı; contango farkı doğrudan `theoretical`'e girdi.

**Kanıt (dördü bağımsız, 2026-08-15/16 ölçümü):**

| Test | Sonuç |
|---|---|
| Kırılma anı | 07-29 07:20Z prim −0.43 → 10:09Z prim −1.91; ons **+%1.18**, Kapalıçarşı **−%0.32**, kur sabit |
| Kontrat merdiveni | `GCQ26` 4380.40 · `GCV26` 4403.70 · **`GCZ26` 4437.30**; `GC=F` hafta içi = GCZ26 |
| Truncgil spot ons | **$4,376.71** → GCZ26 bunun **%1.39** üstünde |
| Seviye farkı bandı | 07-07…07-28: **+0.47…+0.78** (N=15) → 07-30…08-14: **+1.78…+1.93** (N=13) |

Kırılma öncesi/sonrası bantların ikisi de ±0.15 puan genişlikte: fiziki altın bir
sabah spota karşı %1.25 iskonto yapıp üç hafta orada durmaz — vadeli taşıma maliyeti
tam olarak bunu yapar. **Günlük bar aynı anda hiç kırılmadı** → sorun `GC=F`'te değil,
canlı uçtaki kontrat işaretçisinde.

**Üretimdeki zararı:** `|prim| > %1.5` alarmı 08-11, 08-12, 08-13, 08-14'te ateşledi ve
**dördü de Telegram'a gitti** (`telegram_outbox.jsonl` + chat export ile doğrulandı).
Gerçek prim o günlerde −0.22…−0.62 idi. 07-29 raporu hareketin **−%1.41'ini
"Kapalıçarşı primi"ne** yazdı — Kapalıçarşı hiçbir şey yapmamıştı.

### A) Karar: ons **Truncgil spot**'tan alınır, yfinance ons'una YEDEK OLARAK BİLE düşülmez

`config.yaml sources.truncgil.keys.ons: "ons"` + `archive_fetch` ons'u oradan okur;
yfinance yalnız **kur** için kalır. `parse_tr_number` `$` işaretini düşürür (Truncgil
ons'u `'$4.376,71'` biçiminde veriyor; TL alanlarında işaret yok).

**Neden Truncgil:** ons ile gram **aynı kaynaktan ve aynı zaman damgasıyla** gelir →
kaynaklar arası zaman kayması da biter. Yeni bağımlılık yok, ek HTTP çağrısı yok.

**Neden sessiz yedek YOK:** yanlış bir ons, ons'suzluktan kötüdür — hatayı geri
getirirdi. Truncgil düşerse `gram_has` da düşer (ölçüldü 2026-07-29: geçersiz
kayıtların 20/20'sinde 8 alan birden boştu) → kayıt zaten geçersiz; ayrı bir ons
yedeği hiçbir şey kurtarmaz.

**Doğrulama:** canlı çekim → CSV → DB tam zinciri prim **−0.463%** üretti (kırılma
öncesi rejim: −0.47…−0.77).

### B) Karar: kirli pencere **z tabanından düşülür** (silinmez, düzeltilmez)

`stats.prim_kirli_pencereler` — 2026-07-29T10:00Z → 2026-08-17T00:00Z arası kayıtlar
`indicative=1` + `reason="kirli_kaynak:…"` işaretlenir; `prim_series` ve
`count_valid_prim_days` ikisi de dışlar.

**Neden zorunlu — z-skor GENİŞLEYEN pencere** (`calc.zscore` + `db.prim_series`), yani
kirli günler asla dışarı çıkmaz. Gerçek arşiv üzerinde A/B ölçümü:

| | geçerli gün | z tabanı std | **tespit eşiği** |
|---|---:|---:|---:|
| Kirli bırakılırsa | 34/60 | 0.609 | **1.22 puan** |
| Kirli düşülürse | 20/60 | 0.123 | **0.25 puan** |

Detektör **~5 kat sağırlaşıyordu**: gerçek 1 puanlık bir Kapalıçarşı kopuşu —
kapının var oluş sebebi — z=−1.12 verip hiç ateşlemezdi. Bant ayrıca merkezden
kaymıştı (`[−1.96%, +0.13%]`): alt taraf kör, üst taraf aşırı hassas.

**"Beklesek seyrelir mi?" — hayır.** 760 geçerli günde (≈Aralık 2028) eşik hâlâ 0.39p,
temiz referansın (0.22p) ~2 katı. Bekleme bir seçenek değil.

**Neden CSV düzeltilmedi:** `data/archive/*.csv` HAM GÖZLEM kaydıdır. O anki gerçek
spot ons'u bilmiyoruz (yalnız günlük kapanış bar'ı var, o da gün-içi gözlem değil).
Ham veriyi tahminle yeniden yazmak ölçümü uydurmaya çevirirdi.

**Neden kural KOD'da, DB'de değil:** `insert_prim` INSERT OR REPLACE ve `import_all`
**her gün tüm arşivi baştan okuyor** — DB'de elle işaretlemek bir sonraki Actions
koşumunda sessizce silinirdi (ölçüldü 2026-08-16).

**Bedeli:** kapı **~2026-09-16 → ~2026-10-02** (≈16 gün). Kabul edildi: 16 gün
gecikme, kalıcı sağır bir detektöre karşı ucuz.

### Regresyon zırhı
7 mutasyonun **7'si yakalandı** (ons'u yfinance'e geri al · `$` temizliğini kaldır ·
config anahtarını sil · kirli işareti uygulama · sebebi yazma · pencere sınırını
gevşet · pencere listesini boşalt). Test 851 → **855**.

### Kapsam dışı bırakılanlar (bilerek)
- `src/collector.py` hâlâ yfinance ons'u kullanıyor. **Hiçbir yerde koşmuyor**
  (üretim Actions push-only); test edilemeyen ölü bir yolu değiştirmek tutarlı
  bırakıp belgelemekten kötü. Oracle Cloud'a geçilirse **önce burası düzeltilecek.**
- Uzlaşı paneli, hafta sonu beklentisi, kapsama metriği: ölçüldü, kusurlu, ama
  aktif zarar üretmiyor → bu ADR'nin kapsamında değil (bkz. denetim notları).

**Tekrar gözden geçir:**
- Truncgil `ons` alanı kaybolur/şema değişirse (koruma testi düşer).
- Bir sonraki COMEX roll'ü **~2026-11-25** (yılda 5: Oca-Mar-May-Tem-Kas). Truncgil
  spot kullanıldığı sürece etkilenmemeliyiz — o tarihte prim serisinde basamak
  OLMADIĞI doğrulanacak (TAKVİM'e işlendi).
- Eşiğin kendi kalibrasyonu ayrı iştir: temiz seride bile `|z|>2` bandı dar
  (`[−0.86, −0.37]`) → **~2026-09-25 EŞİK KARARI** maddesi geçerliliğini koruyor.

---

## #012 — 2026-08-11 — Bekleyen 4 karar kapatıldı: kademe KAPALI, gölge kol YAPILMAYACAK, makas eşiği maddi, reel faiz tabanı şeffaf

**Tetikleyen:** Mert: *"bunları gerekli görüyorsan uygula veya uygulama … profesyonel
bir BIST yatırımcısı gibi düşünebilirsin, nihai kararını ver ve gerekliyse harekete geç."*
Denetimden (`ai/denetim-2026-08-11.md`) çıkan 4 açık karar aylardır TAKVİM'de
bekliyordu. Hepsi **ölçümle** kapatıldı — tercihle değil.

### A) ÇEKİRDEK KADEME → **KAPALI** (#010-B kapandı)

| Ölçüm | Değer | Kaynak |
|---|---:|---|
| Kural `reel_mevduat > %10` tabana farkı | **+1.34p** | `data/aday_taramasi.json` |
| Aynı kuralın ortalama gram kazancı | **%-0.64** | taban −1.987 + fark 1.343 |
| Başa baş (çekirdek eşiği) | **0.00** (= +1.99p fark) | `esik_cekirdek_puan` |
| N · t | 22 · **1.03** | tarama |
| 0.75× kademenin beklenen aylık maliyeti | **-%0.16 gram** | 0.25 × (−0.64) |
| Canlı örneklem-DIŞI (07-27 → 08-10) | **-%1.55 gram** | denetim §4 |
| Kuralın canlı ateşleme oranı | **30/30 tahmin** | `predictions` |

**Karar:** `karar.cekirdek.kademe_aktif: false`. Hüküm daima `AL` (1.00×).

**Neden — yatırımcı gerekçesi:** amaç fonksiyonu **terminal gram** ve gram/TL'nin
sürüklenmesi pozitif. Alımı sistematik geciktirmek, o sürüklenmeye karşı örtük bir
kısa pozisyondur; ancak gerçek bir zamanlama kenarı varsa haklı çıkar. Burada kenar
yok: kural örneklem-**içi** (yani olabilecek en iyimser) ölçümde bile ortalama
**negatif** getiriyor — başa başı geçmiyor, yaklaşmıyor bile. t=1.03 gürültü.
Projenin kendi tarama raporu zaten yazıyordu: *"farkı bu kadar yenemeyen bir kural,
alımı geciktirdiği her ay gram kaybettirir."* İki tarafta da kayıp varsa karar
kolaydır.

**"Küçük ve simetrik, tutalım" argümanı ÖLÇÜMLE düştü:** simetrik değil. Üst kademe
(`reel_mevduat < 0` → 1.25×) politika faizi %40'ta çakılıyken erişilemez; canlıda
**30/30 kez alt kademe** ateşledi. Yani pratikte tek yönlü bir "az al" kuralıydı.

**Mekanizma SİLİNMEDİ, kapıya bağlandı.** Çarpanlar config'te duruyor; açılma şartı
önceden kayıtlı ve sonradan gevşetilmez: **tarama, kuralı N≥30 ve |t|≥2 ile
+1.99p'nin üstünde göstermeli.** Kapı açıldığı gün karne metriği de alım-şiddeti
uzayına taşınmalı — bugünkü `gram.hukum_dogru_mu` SAT uzayında tanımlı ve `AL_*`
için özdeş 0 üretir (L-010). Doğru formül şudur ve kanıtı basittir: ertelenen
`(1−m)` pay giriş yerine çıkış fiyatından alınır, dolayısıyla

> `gram_etkisi_cekirdek = (1 − carpan) × gram_carry_kazanc_pct`

(`gram_carry_kazanc_pct` zaten `(giriş/çıkış)×(1+net faiz) − 1` olarak hesaplanıyor).
Kontrol: id=19 tahmininde carry −4.871 → 0.25 × (−4.871) = **−1.22%**, ölçülen
DCA sonucuyla (−1.55%) aynı işaret ve mertebe.

**Kapatma SESSİZ değil:** kural yine değerlendirilir, hüküm bloğu "kademe AÇIK
olsaydı alım 0.75× olurdu" + kapatma gerekçesini yazar. "Yapmadım" ile "yapacak bir
şey yoktu" ayrı şeylerdir.

### B) GÖLGE KOL → **YAPILMAYACAK** (#008-B kapandı)

Bu bir erteleme değil, **ölçüme dayanan bir ret**. İki kol ayrı ayrı incelendi:

**Taktik gölge kol → bilgi üretemez.** `karar.taktik_hukum`, kapı AÇIK olsa bile
`beklenen_gram_kazanc_pct` üreticisi bağlı olmadığı için `TUT` döner
(`_URETICI_YOK` dalı). Üretici yokluğu unutma değil ölçüm sonucudur: 458 haftalık
asof üzerinde 14 aday tarandı, en iyisi +1.4p, gereken +3.18p (ADR #007-H). Yani
gölge taktik kol **%100 TUT** kaydeder — bugünkü dejenere karnenin birebir aynısı.
Sıfır bilgi için paralel bir kayıt yolu kurmak, karneye bulaşma riskini bedavaya
almaktır.

**Çekirdek gölge kol → gereksiz.** Kural **deterministik** ve girdilerinin TAMAMI
zaten saklanıyor (`predictions.ozellikler_json` her tahminin tam özellik vektörünü
tutuyor). Karşı-olgu bu yüzden **tam olarak yeniden üretilebilir**; `tahmin_backfill`
bunu 458 haftalık asof üzerinde zaten yapıyor. Canlı gölge kol, arşiv büyüdükçe
taramayı yeniden koşmanın vermediği hiçbir bilgi vermez.

**Kural (genelleştirilebilir):** gölge kol, karşı-olgu **yeniden üretilemediğinde**
gerekir (saklanmayan girdi, sürüklenen model ağırlığı, dış duruma bağlı karar).
Deterministik + girdisi saklanan bir kuralda gölge kol, backtest'in pahalı ve
kırılgan bir kopyasıdır. **Yeniden gözden geçir:** taktik kola gerçek bir
beklenen-kazanç üreticisi bağlanırsa (o gün karşı-olgu artık trivially TUT olmaz),
ya da karar saklanmayan bir girdiye bağlanırsa.

### C) `makas > p90` → **MADDİ TABAN EKLENDİ**

Ölçüm (2026-08-11, N=313 FRESH kayıt):

| | Değer | Medyana oran |
|---|---:|---:|
| Medyan | %0.0146 | 1.00× |
| p90 | %0.0158 | **1.08×** |
| Gözlenen en yüksek | %0.0260 | 1.78× |

Yüzdelik, **tanımı gereği** kayıtların %10'unu aşar. Seri dar ve durağan olduğu için
"p90 aşıldı" cümlesi piyasa hakkında hiçbir şey söylemiyordu: alarm her gün
ateşliyordu (teslim edilen 19 bildirimin **12'si** buydu, hepsi "%0.016 > p90
(%0.016)") ve günlük tavanı (6) yiyordu. **L-010'un aynısı: girdiden bağımsız aynı
çıktıyı üreten bir "ölçüm" ölçüm değil KİMLİKTİR.**

**Karar:** kural susturulmadı, eşiği maddi hâle getirildi —
`spread_min_medyan_carpani: 2.0`. Makas hem p90'ı hem **medyanın 2 katını** aşmalı.
Bu eşikte 313 kaydın **hiçbiri** ateşlemezdi; doğrusu da bu, çünkü bu dönemde makas
patlaması olmadı. Gerçek bir stresde (kaynak makası açar) alarm yine çalışır.

**Yan düzeltme:** makas tabanı artık yalnız **FRESH** kayıtlardan hesaplanıyor.
Filtre yoktu; hafta sonu/indicative satırlar yüzdeliği besliyordu, oysa z-skor kapısı
yalnız FRESH sayıyor — aynı arşivden iki farklı taban çıkıyordu.

### D) REEL FAİZ TABANI → **RAPORDA GÖRÜNÜR**

Çekirdek kolun tek kapı değişkeni ve rapor dayanağını hiç söylemiyordu. `ozellikler.py`
bilinçli olarak **12 ay beklentiyi** kullanıyor (TÜFE 8 aydır bayat; sessiz yedeğe
düşme replay'de kesişim kuralını ihlal ederdi) — doğru bir mühendislik seçimi, ama
sonuç tamamen bu seçime bağlı:

| Taban | Değer | Kural |
|---|---:|---|
| 12 ay beklenti (kullanılan) | **%12.67** | tetikler (>%10) |
| Gerçekleşen TÜFE (2025-12) | **%6.69** | tetiklemez |

Rapor artık ikisini de yazıyor. Karar değişmedi, **şeffaflık** eklendi: okuyan
sayının hangi seriden geldiğini ve alternatifin ne vereceğini görüyor.

### E) TELEGRAM KOMUTLARI → **KABUL + BELGELE** (seçenek a)

Üretim push-only; `/hukum` `/karne` `/grafik` yanıt vermiyor (long-polling'e kalıcı
süreç lazım, cron'da yok). Üç seçenek vardı: (a) kabul + net uyarı, (b) `archive.yml`'a
"bekleyen komutları yanıtla" adımı (gecikme ≤ ~3 saat), (c) kapsamdan çıkar.

**Karar: (a).** Gerekçe risk/getiri:

| | Ölçüm |
|---|---|
| Talep | Chat export'ta **4 ayda 3 komut** (2026-07-09 ×2, 07-26) |
| İçerik fazlalığı | Komutların döndüğü her şey (HÜKÜM · karne · grafik · durum) zaten **günlük push raporunda** var |
| (b)'nin maliyeti | `getUpdates` döngüsü **archive.yml**'a girer — 13 günlük sessiz kesintinin yaşandığı kritik yol. Yeni bir arıza modu, yeni bir `continue-on-error` yüzeyi |

Ayda ~0.75 kullanımlık bir kolaylık için, az önce onardığımız yola yeni bir arıza
modu eklemek kötü bir takas. **Yeniden gözden geçir:** komut kullanımı ayda 5'i
geçerse (b) yeniden değerlendirilir.

### F) Z-SKOR PROVASI İLK KEZ OKUNDU (karar değil, ÖLÇÜM — ~09-05'i besler)

TAKVİM'deki "~2026-08-01 prova birikimini oku" işi yapıldı. N=17 prova
(18 olmalıydı; 08-06'daki iptal edilen koşum bir satır götürdü):

| Bulgu | Değer |
|---|---|
| **İki taban (kayıt/gün) aynı kararı verdi** | **17/17 prova** — ampirik fark YOK |
| `prim |z|>2` tetiklerdi | **6/17 (%35)** — nominal beklenti ~%5 |
| `çeyrek |z|>2` tetiklerdi | **3/17 (%18)** |
| `std_gun` büyümesi | 0.081 → 0.589 = **7.2×** |
| Gözlenen en uç z | **−6.06** (gün) / **−6.30** (kayıt) |

**Yorum:** z=−6 bir anomali değil, **kısa taban artefaktı**. 07-29'da prim −0.63 →
−2.43 rejim kayması yaptı; 16 günlük dar bir tabana (std 0.081) karşı ölçülünce z
patladı. Taban genişledikçe (std 7.2×) aynı sapma normalleşti. Bu, provanın tam
olarak yakalaması için var olduğu şey.

**İki sonuç, ikisi de ~09-05'e taşınıyor (şimdi karar VERİLMİYOR — 17 örnekle karar
vermek, kapattığımız kademe hatasının aynısı olurdu):**
1. **Taban seçimi ampirik olarak fark etmiyor** → ilkeye göre seçilecek. Bugünkü
   eğilim **gün tabanı**: (i) kapının kendisi gün sayıyor, iki farklı taban bir
   sistemde karışmamalı; (ii) gün içi prim kayıtları seri korelasyonlu, onları
   bağımsız örnek saymak etkin N'i şişirir ve |z|'yi olduğundan büyük gösterir;
   (iii) kayıt tabanı Actions throttling'ine rehin (29 kayıtlı gün, 6 kayıtlı günün
   5 katı ağırlık alır) — bu bilgi değil örnekleme artefaktı.
2. ⚠️ **Kapı açılışında alarm seli riski.** %35 tetikleme oranı × günlük tavan 6 →
   z alarmları diğerlerini bastırabilir. `alerts.prim_z: 2.0` eşiği ~09-05'te
   **prova dağılımına bakılarak** yeniden değerlendirilmeli.

**Doğrulama:** 851 test yeşil (845 → 851). 5 kontrollü mutasyon; biri
(makas FRESH filtresi) **ilk turda kaçtı** — sebebi L-016'nın kendisiydi: hiçbir test
filtreyi DB üzerinden görmüyordu. Rejimli veriyle (FRESH %0.010 · bayat %0.100) yeni
test yazıldı, mutasyon yakalandı. Uçtan uca render (üretim DB'si): hüküm bloğu
`NORMAL AL` + kapatma gerekçesi, makro bölümü taban + duyarlılık satırı.

**Tekrar gözden geçir:** (a) tarama kuralı N≥30 ve |t|≥2 ile +1.99p'nin üstüne
taşırsa kademe yeniden açılır; (b) taktik kola beklenen-kazanç üreticisi bağlanırsa
gölge kol kararı yeniden değerlendirilir; (c) TÜFE serisi tazelenirse reel faiz
tabanı seçimi yeniden tartışılır; (d) makas serisi rejim değiştirirse (kaynak
değişimi, gerçek stres) 2.0× çarpanı yeniden ölçülür.

---

## #011 — 2026-08-11 — Bildirim hattı: kaçış + izolasyon + görünürlük (sessiz arıza sınıfı kapatıldı)

**Tetikleyen:** Mert: *"proje uzun zamandır kendi çalışıyor, kaliteli sonuçlar
üretebilmiş mi kontrol et."* Denetim ölçtü: **13 gün boyunca hiçbir anomali
bildirimi gitmemiş** (2026-07-29 → 08-10, 125 Actions koşusu, hepsi yeşil).
Detay: `ai/denetim-2026-08-11.md`, ders: **L-018**.

**Ölçüm (kanıt zinciri değil, doğrudan deney):** üretimdeki metin canlı
Telegram API'sine iki kez gönderildi —

| Sürüm | HTTP | Telegram cevabı |
|---|---|---|
| Kaçışsız (eski kod) | **400** | `can't parse entities: Unsupported start tag "1.5)" at byte offset 107` |
| Kaçışlı (yeni kod) | **200** | ok |

### Karar — düzeltme METNE değil MEKANİZMAYA yapıldı

Alternatif A (reddedildi): iki metindeki `<` işaretini elle temizle. Ucuz ama
sınıfı kapatmaz — gelecekte eklenen her eşik metni aynı çukura düşebilir.
Alternatif B (seçildi): dört katmanı birden kapat.

1. **Kaçış şablonun içinde** — `notify.tg_kacir` (`html.escape`, `quote=False`);
   `_format_alert` dinamik alanların hepsini kaçırır. Metinler olduğu gibi
   kaldı; artık `(|%|<1.5)` doğru görüntüleniyor.
2. **Gönderim izolasyonu** — `notify._gonder` her bildirimi bağımsız dener;
   biri patlarsa arkasındakiler yine gider.
3. **Damga geri alma** — `notify.damgayi_geri_al`: gönderilemeyen bildirimin
   `last_sent` damgası ve tavan sayacı geri alınır, yoksa 24s soğuma onu
   kalıcı susturur.
4. **Görünürlük** — `notify.saglik_guncelle` ardışık hatayı `alert_state.json`'a
   yazar (arşiv workflow'u zaten commit'liyor); `report.bildirim_saglik_metni`
   bunu günlük raporun EN ÜSTÜNE basar: *"🔴 BİLDİRİM HATTI ARIZALI: N ardışık
   gönderim hatası… GİTMİYOR."*

**Neden 4. madde şart:** 1-3 arızayı önler, 4 arızayı **görünür** kılar. 13 günü
13 gün yapan şey hatanın kendisi değil, hiçbir yerin "gönderemedim" dememesiydi.
`continue-on-error: true` korundu (commit adımı bloklanmasın) ama artık tek
görünürlük kanalı o değil.

### Yan karar — `daily.yml` ayrı concurrency grubuna alındı

Eskiden ikisi de `repo-commit` grubundaydı ve bir **kilit test bunu koruyordu**
("farklı gruplarda push çakışır"). Ölçüm dengeyi tersine çevirdi: GitHub grup
başına yalnız bir bekleyen koşu tutar, dolayısıyla 15 dk'lık arşiv koşusu sırada
bekleyen günlük raporu **düşürüyor**. 2026-08-06'da oldu: rapor yok, `asof=08-05`
tahmini hiç yazılmadı, Telegram'a tek mesaj gitmedi — **günün tamamı kayboldu.**

Push yarışı ucuz ve geri alınabilir (rebase + retry); iptal edilen koşu değil.
Grup ayrıldı, karşılığında push döngüsü 3 → **5 deneme + artan bekleme** yapıldı.
Eski test susturulmadı, **daha güçlü sözleşmeyle değiştirildi**
(`test_gunluk_rapor_arsivleyiciyle_AYNI_GRUPTA_DEGIL` +
`test_push_yarisi_rebase_denemesiyle_karsilaniyor`).

### Yan karar — sessiz düşme yasağı iki yerde daha uygulandı

- `karar.kademe_kaniti_satiri`: `data/aday_taramasi.json` yoksa eskiden `[]`
  dönüyordu → satır **7/7 üretim raporunda hiç basılmadı**, oysa STATE.md
  "her gün beyan ediyor" diyordu. Artık dosya yoksa bunu **söylüyor**.
  (Dosyanın kendisi de repoya alındı.)
- `chart._kova_edge_line`: gösterge NÖTR iken artık ölçüm satırı basılmıyor.
  Eskiden ikili seçim vardı ve nötr RSI, "RSI aşırı alım" kovasının ölçümünü
  taşıyordu — yürürlükte olmayan bir koşulun kanıtı.

**Doğrulama:** 839 test yeşil (+24). 6 kontrollü mutasyon uygulandı
(kaçış, izolasyon, damga, defter, uyarı metni, rapora bağlama) → **6/6 yakalandı**.
Ayrıca canlı Telegram deneyi yukarıdaki tabloda.

**Tekrar gözden geçir:** (a) Telegram `parse_mode` politikası değişirse
(`MarkdownV2`'ye geçilirse kaçış kümesi başkadır); (b) günlük raporun push
denemesi 5'te de tükeniyorsa concurrency ayrımı yeniden tartışılır; (c) z-skor
kapısı ~2026-09-14'te açıldığında `prim_z` ilk kez ateşlenecek — **o gün canlı
doğrulama yapılmalı** (STATE TAKVİM'e işlendi).

---

## #010 — 2026-07-29 — Grafik ölçümü faz artefaktından arındırıldı + AÇIK kolun eşiği görünür kılındı

**Tetikleyen:** Mert: *"bu projede çok önemsediğim şey grafik analizine göre
tahmin yürütülmesi, bunun için kontrol sağlamanı istiyorum."* Denetim iki ayrı
ölçüm hatası buldu; ikisi de aynı kökten: **eşik, ölçümün gürültüsünden küçüktü.**

### A) `chart.measure_edge` artık tabanı TÜM fazlardan ölçüyor (ADR #007-E kapatıldı)

#007-E'de tespit edilip Backlog'a yazılan düzeltme koda taşındı
(`chart.phase_matched_edge_baseline`). Kural: **ölçüm eşiği faz yayılımından
küçük olamaz** → `esik = max(min_anlamli_fark_puan, yayilim)`.

Sonuç — `reports/grafik_dogrulama.md` yeniden üretildi (GC=F, 2653 bar):

| | ÖNCE (tek faz) | SONRA (faz eşleşmeli) |
|---|---:|---:|
| "zayıf kanıt" satırı | **10** | **1** |
| "kenar yok" satırı | 14 | 23 |

Ölçülen faz yayılımı: 1ay **1.0p** · 3ay **4.1p** · 6ay **7.4p**. Config'teki
`min_anlamli_fark_puan: 1.0` eşiği 3-6 ay ufuklarında gürültünün 4-7 katı
altında kalıyordu; o ufuklardaki her "zayıf kanıt" satırı artefakttı.

**Hüküm: grafiğin ölçülmüş bir yön kenarı YOK.** Tek ayakta kalan satır
`RSI aşırı satım · 1ay · +2.0p` (N=16, in-sample ve OOS ikisi de "ölçüm
yetersiz") — 54 karşılaştırmada 1 zayıf satır, Bonferroni'den sonra kanıt değil.
Bu bir başarısızlık değil **sonuçtur**: seviyeler kademe/stop geometrisi olarak
kalır, yön iddiası olarak kullanılmaz. Rapordaki dil zaten buna göreydi; artık
ölçüm de dili doğruluyor.

### B) Aday taraması ÇEKİRDEK eşiğini de raporluyor — ve açık kol eşiği geçemiyor

`tahmin_backfill` yalnız **taktik** eşiğine (taban + gidiş-dönüş = +3.18p) göre
hüküm veriyordu. Ama üretimde AÇIK olan kol **çekirdek** ve onun eşiği daha
düşük (+1.99p, makas ödenmez). Yani sistemin fiilen kullandığı kol, kendi
eşiğine göre hiç denetlenmemişti.

Ölçüm (458 haftalık asof, 1ay ufku, tüm fazlar):

| Kural | Fark | N | t | Taktik | Çekirdek |
|---|---:|---:|---:|:--:|:--:|
| `kur oynaklık > %25 (şok)` | +2.85p | 6 ⚠️ | +1.01 | ❌ | ✅ |
| **`reel_mevduat > %10`** (kademeyi üreten kural) | **+1.34p** | 22 ⚠️ | +1.03 | ❌ | **❌** |
| `reel_mevduat < 0` (1.25× kademesi) | −1.06p | 34 | −0.80 | ❌ | ❌ |

**Sonuç: çekirdek kolun İKİ kademesi de kendi başa baş eşiğinin altında.**
`reel_mevduat > %10` tetiklendiğinde satmanın ölçülen gram kazancı hâlâ
**%−0.64** — yani alımın %25'ini ertelemek, ölçüme göre o ay ~%0.16 gram
kaybettirir. t≈1.0 olduğu için bu kayıp da gürültüden ayırt edilemez.

**Karar: kademe KALDIRILMADI, ama her rapor kendi kanıt durumunu beyan ediyor.**
Hüküm bloğuna satır eklendi (`karar.kademe_kaniti_satiri`), veri
`data/aday_taramasi.json`'dan okunur → tarama tazelenince satır kendini günceller:

> _**Kademenin kanıtı:** başa baş eşiği +1.99p · kural `reel_mevduat > %10`
> örneklem-içi ölçümde **+1.34p** (N=22, t=+1.03) → eşiğin **ALTINDA**._

**Neden kaldırılmadı:** kademeyi kapatmak (`carpan=1.0`) Mert'in gerçek alım
davranışını değiştirir; bu bir mühendislik tercihi değil onun kararıdır. Usta'nın
işi ölçümü görünür kılmaktı, kararı almak değil. Seçenek STATE.md TAKVİM'inde
👤 satırı olarak duruyor.

**Tekrar gözden geçir:** (a) canlı karne ≥30 çözülmüş tahmine ulaşınca — o zaman
kademe örneklem-DIŞI ölçülebilir; (b) yeni bir aday çekirdek eşiğini N≥30 ve
|t|≥2 ile geçerse.

### C) Koruma disiplini: 8 mutasyon, 8'i yakalandı — biri ilk turda KAÇTI

`cekirdek_gecti` bayrağını sabit `False` yapan mutasyon ilk turda testlerden
geçti: eşik testlerinin tamamı elle yazılmış fixture üzerinden çalışıyordu,
üreticinin bayrağını hiçbiri doğrulamıyordu. Düz üstel sentetik seride her
adayın farkı özdeş 0 çıktığı için üretici testi de vacuous olurdu.
Çözüm: iki rejimli sentetik seri (`_doldur_rejimli`) + "kurgu eşiği aşan aday
üretmediyse testi düşür" assert'i. → **L-016**

## #009 — 2026-07-27 — Regresyon zırhı: testler ARAÇ DEĞİL, devrin kendisi

**Tetikleyen:** Mert: *"yakın zamanda Claude Code aboneliğim bitecek... ileride
düşük modelli yapay zekalar projemi bozmasın."* Bu, PROJECT.md'deki
araç-bağımsızlık kısıtının (ADR #001/#002) doğal sonucu: kurallar taşınabilir
hâle getirildi, **ama kuralların uygulandığını hiçbir şey doğrulamıyordu.**

### A) Testin işi değişti: "hata bulmak" değil, "sözleşmeyi kilitlemek"

Mevcut 299 test doğruydu ama tamamı **birim** seviyesindeydi. Bu projede
yaşanan en pahalı arızaların HİÇBİRİ birim seviyesinde değildi:

| Arıza | Nerede | Birim testi görür müydü? |
|---|---|---|
| `history_daily` 17 gün donuk (#004) | parçalar arası (pipeline'a bağlı değildi) | hayır |
| `quarter_z` daima None (#006-C) | üretici ↔ tüketici | hayır |
| `daily_job` altı adımı yutuyor (#008 K-6) | süreç çıkış kodu | hayır |
| `asof` koruması bağlanmamış (L-011) | çağrı yolu | hayır |
| Karne totolojisi (L-010) | metriğin tanımı | hayır |

Yeni paket bu boşluğu hedefler: **491 yeni test, 16 dosya, 8138 satır** →
toplam **804 test**. Ağırlık merkezi birim değil **sözleşme**:

| Sözleşme | Neyi kilitler |
|---|---|
| `test_uctan_uca` | Zincirin tamamı: izole kökte `daily_job.run()` (ağ kapalı, sentetik veri) |
| `test_sozlesme_config` | 149 `cfg[...]` zinciri çözülüyor mu · ölü anahtar var mı · **önceden kayıtlı eşikler gevşetilemez** |
| `test_sozlesme_sema` | Şema ↔ dump ↔ Actions stateless döngüsü; değiştirilemezliğin kolon kolon kapsamı |
| `test_sozlesme_workflow` | Üretim = 2 YAML: `restore→iş→dump→commit` sırası, `continue-on-error` yokluğu |
| `test_sozlesme_gizlilik` | L-005 (satır-sonu yorumu), iki yönlü `check-ignore`, sır sızıntısı |
| `test_yapisal_korumalar` | Tek asof/eşik/maliyet/teorik-gram kaynağı; `_hata` yolu (AST ile) |
| `test_ag_izolasyonu` | Karar yolu **soket kapalıyken** çalışmalı; ağ hangi modüllerde olabilir |
| `test_dejenere_metrik` | L-010 avı: metrik 11 senaryoda değişebiliyor mu; eşik config'ten mi |
| `test_dokuman_tutarliligi` | Devir paketi: köprüler, `ai/` yapısı, L/ADR numara uzayı, belgelenen komut |
| `test_saf_cekirdek_ozellikleri` | Formül değişmezleri (ölçek/kaydırma bağımsızlığı, tek eşik) |

**Neden bu kadar çok "yapısal" test:** L-011 zaten kanıtladı ki davranış testi
yetmiyor — "bu korumayı atlayan bir yol var mı?" sorusunu da **testin** sorması
gerekiyor. Bu yüzden AST/metin taraması meşru bir test tekniği olarak kabul
edildi (tek asof kaynağı, tek eşik kaynağı, `import requests` nerede olabilir).

### B) Testin kendisi ölçüldü — 20 mutasyon, 20 yakalama

"Testleri yazdım, geçiyor" bu projede kabul edilebilir bir cümle değil (L-012).
20 kontrollü mutasyon uygulandı ve her biri `try/finally` ile geri alındı:
`asof` filtresini gevşet · hafta sonu filtresini sil · `taktik.aktif: true` ·
z kapısını 60→20 · tabloyu dump listesinden düşür · `predictions.id`'yi çıkar ·
imza sırasını değiştir · `karar.py`'ye ağ ekle · kritik adım etiketini kaydır ·
ölçülebilirlik bayrağını sahtele · gram carry'yi TL farkına çevir · eşiği koda
göm · DELETE korumasını kaldır · trigger'dan kolon düşür · `insert_tick`'i düz
INSERT yap · dump'ı düz INSERT'e döndür · `backup.sh`'a push ekle · script'i sil.
**20/20 yakalandı.** → Ders **L-015**.

### C) Denetimde bulunan 4 açık kapatıldı

| Açık | Ölçüm | Düzeltme |
|---|---|---|
| `ticks` her koşumda yeniden yazılıyor | dump'ta 15 999 satır, **tekil 1 663** (9.6×); en eski satır 23 kopya | `ticks(ts_utc, source, symbol)` benzersiz indeks + `INSERT OR IGNORE`; `db.tekil_tick_indeksi()` mevcut DB'leri **önce onarıp sonra** indeksi kuruyor → L-013 |
| Tahmin kaydı **silinebiliyordu** | trigger yalnız UPDATE'i engelliyordu | `trg_predictions_nodelete` → L-014 |
| `kaynak`/`model_version` korumasız | bu iki kolon kaydın hangi karneye sayıldığını belirliyor | UPDATE trigger listesine eklendi; trigger'lar artık `DROP+CREATE` (tanım değişince `IF NOT EXISTS` eski kapsamı bırakıyordu) |
| `deploy/altin-backup.service` → olmayan script | STATE backlog'unda duruyordu | `scripts/backup.sh` yazıldı: yalnız WAL-güvenli anlık görüntü; git/ağ/silme YOK (L-007'nin tekrarı engellendi) |

**Veri sonucu:** `data/altin.sql` **33 699 → 19 369 satır** (4.98 → 2.8 MB).
Tekilleştirme **commit'li dump'ın kendisinden** yapıldı, bayat yerel sqlite'tan
değil (L-009). Kopyalar birebir aynıydı (aynı anahtarda farklı değer taşıyan
tek satır yok) → bilgi kaybı sıfır. `restore → dump` gidiş-dönüşü commit'li
dosyayla **bayt bayt aynı** (sabit nokta doğrulandı).

**Geriye uyum:** dump artık `INSERT OR IGNORE` yazıyor ve `restore` benzersiz
indeksi **yükleme bittikten sonra** kuruyor. Böylece eski bir commit'e dönüp
`python -m src.restore_db` çalıştırmak hâlâ çalışıyor — aksi halde her tarihsel
dump `IntegrityError` verirdi.

### D) Neden bu kadar yatırım — ve sınırı

Testler bu projede **bakım maliyeti değil, devir belgesidir**: yeni bir araç ya
da daha zayıf bir model geldiğinde kuralları okumasa bile ihlal ettiği anda
kırmızı görür. Yine de sınır açık: test paketi **doğruluğu** değil
**sözleşmeyi** korur. Bir formülün finansal olarak doğru olup olmadığını hâlâ
ölçüm söyler (ADR #007-B/H); testler yalnız o ölçümün sessizce değiştirilmesini
engeller.

**Tekrar gözden geçir:** (a) `predictions` yazımı başlayınca (2026-07-27 akşamı)
`test_veri_butunlugu`'ndaki tahmin tutarlılık testleri gerçek veriyle anlam
kazanır; (b) taban satır sayıları (`TABANLAR`) veri büyüdükçe **yükseltilir,
asla düşürülmez**; (c) gölge kol kararı verilirse (ADR #008-B) karne testleri
"ölçülemez" dalından "ölçülür" dalına taşınmalı.

---

## #008 — 2026-07-27 — Denetim: karne bir totolojiydi; ölçülemezlik GİZLENMEK yerine RAPORLANIYOR

**Tetikleyen:** Karar motoru (ADR #007) push edilmeden önce uçtan uca denetim.
Bulunanların hepsi ölçümle kanıtlandı; iddiaların hiçbiri "muhtemelen" değil.

### A) EN ÖNEMLİ BULGU — karne hiçbir şey ölçmüyordu

`gram.hukum_dogru_mu` iki dala ayrılır: `SAT*` ise "satmak kazandı mı", **değilse**
"satmamak doğru muydu". Taban daima `hukum_dogru_mu("TUT", …)`. Sistemin gerçekte
üretebildiği hükümler ise yalnız `{AL_COK, AL, AL_AZ}` (çekirdek) ve `TUT`
(taktik, kapı kapalı). **Hiçbiri `SAT` ile başlamıyor.** Sonuç:

| hüküm | isabet_farkı | gram_etkisi |
|---|---:|---:|
| AL_COK · AL · AL_AZ · TUT · BEKLE | **+0.00p** | **+0.00%** |

11 farklı gram carry senaryosunda (−40%…+60%) koşuldu; **piyasa ne yaparsa yapsın
aynı.** Bunlar ölçüm değil, fonksiyonun tanımının sonucu — yani **kimlik**.

**Kapı kendi kendini kilitliyordu:** `kapi_durumu` şartı `gram_etkisi > 0` **ve**
`isabet_farki >= 10p`. İkisi de yapısal 0 olduğu için `aktif: true` yapılıp N=35
beslendiğinde bile kapı kapalı kalıyor ve gerekçe *"karnede gram etkisi pozitif
değil"* diyordu. Kapalı kapı → TUT → sıfır skor → kapalı kapı.

**Neden kritikti:** STATE.md'nin takvimi Ekim'de bu tabloyu okuyup *"trade kolu
kalıcı kapalı"* ADR'si yazmayı planlıyordu. O ADR bir ölçüm sonucuna değil, bir
totolojiye dayanacaktı — ve tablo tıpatıp gerçek bir ölçüm gibi göründüğü için
anlaşılmayacaktı.

### B) Karar: totoloji GİZLENMİYOR, BAĞIRILIYOR (döngü henüz KIRILMADI)

Yapılan: `karne_ozeti`'ye `olculebilir_mi` (= en az bir `SAT` hükmü var mı) ve
`sat_hukum_sayisi` eklendi. Ölçülemez durumda:
- `format_karne_md` rakam yerine **"🚫 Bu karne ÖLÇÜM İÇERMİYOR"** yazıyor,
- `format_karar_md` karne satırı **"tabana fark ve gram etkisi ÖLÇÜLEMİYOR"** diyor,
- `kapi_durumu` **"şart sağlanmadı DEĞİL, ölçülmedi"** gerekçesini döndürüyor.

**Yapılmayan (bilerek):** döngüyü kırmak için "gölge kol" (kapı açık olsaydı
üretilecek hükmü ayrıca kaydetmek) gerekiyor. Bu bir tasarım kararıdır ve
**Mert'e bırakıldı** — çünkü (C)'deki sebeple gölge kol da bugün SAT üretemez.

### C) `beklenen_gram_kazanc_pct` üreticisi YOK — ve bu bir unutma değil

`karar.taktik_hukum` bu alanı okuyor; tek üretici olabilecek `gram.engel_ozet`
onu **hiç üretmiyor** (8 anahtar üretiyor, bu yok). `.get()` sessizce `None`
dönüyor → `SAT_25` dalı üretim verisiyle **erişilemez**. Kapı zorla açılarak
doğrulandı: hüküm yine `TUT`.

**Sebep ADR #007-H'de zaten yazılı:** 458 haftalık asof üzerinde 14 aday tarandı,
en iyisi +1.4p (t≈1.4), gereken +3.18p. **Dürüst bir tahminci yok.** Bu yüzden
buraya uydurma bir üretici KOYULMADI; bunun yerine kod artık *"ÜRETİCİSİ BAĞLI
DEĞİL"* diyor ve bunu *"hesaplanamadı"*dan ayırıyor (`beklenen_kaynak` alanı).
`test_uretici_beklenen_gram_kazancini_URETMIYOR` bunu kilitliyor: bir gün gerçek
bir tahminci bağlanırsa test düşecek ve bu dalın kaldırılması gerektiğini
hatırlatacak.

### D) `asof = T−1` garantisi kâğıt üstündeydi

`ozellikler.son_kapali_gun`'da bugünü dışlayan filtre **opsiyoneldi** ve iki
çağıranın hiçbiri onu geçmiyordu; `tahmin.py`'de ayrıca filtresiz ikinci bir
`MAX(date)` kopyası vardı. `daily_job` ise bu adımdan **önce**
`history.update_recent`'ı çağırıyor.

**Ölçüldü (üretim dump'ı):** 2026-07-24 17:25Z koşumunda hem `ohlc_daily` GC=F
hem EVDS `TP.DK.USD.S.YTL` **aynı-gün** satırını içeriyordu → `history_daily`'nin
bugünü almaması için hiçbir engel yok. Bugüne dek patlamamasının tek sebebi,
`update_recent`'ı bağlayan düzeltmenin (`bb5a2ee`, 07-24 20:26Z) ardından yalnız
hafta sonu koşumu olması. **İlk hafta içi koşum 2026-07-27.**

Gerçekleşseydi: özellikler yarım bardan üretilip `predictions`'a DEĞİŞTİRİLEMEZ
yazılacak, ertesi gün aynı satır gerçek kapanışla ezilecekti (`INSERT OR REPLACE`)
→ kayıtlı hüküm bir daha yeniden üretilemez, **ADR #007-G'nin "canlı = replay"
garantisi düşerdi.**

**Karar:** filtre **varsayılan ve zorunlu** yapıldı (filtresiz yol YOK), ikinci
kopya silindi, referans **yerel TR günü** (UTC değil — GC=F 00:00 TR'de kapanıyor).

**Sonradan bulunan EKSİK (aynı gün, re-audit'te):** yukarıdaki düzeltme yalnız
`asof`'u koruyordu; bugünün yarım satırı `history_daily`'ye **yazılmaya devam
ediyordu.** Tabloyu 16 ayrı yer okuyor ve hepsi korumasızdı. En kritiği
`tahmin._fiyat_serisi`: `cozumle`'nin 3 günlük **ÇIKIŞ** ortalaması bugünün yarım
barını içerebiliyordu ve o sonuç `prediction_outcomes`'a yazılıyor.
16 okuma yolunu tek tek yamamak L-008'in ta kendisi olurdu → **kaynak kapatıldı**:
`history.build_history_daily` artık bugünü kesişimden düşürüyor
(`ohlc_hist.update_ohlc_daily` ile simetrik). Kayıp yok — `update_recent` her gün
son 45 günü yeniden çekiyor, bugünün tam barı yarın yazılıyor; canlı fiyata
ihtiyaç duyan tek yol (`notify`) zaten arşiv CSV'sinden okuyor.
Ders **L-011** bu kalıbı kaydediyor: korumayı tüketiciye değil kaynağa koy.

### E) Diğer düzeltmeler

| # | Sorun | Karar |
|---|---|---|
| K-6 | `daily_job`'un altı adımı da istisnayı yutuyordu, süreç daima 0 ile çıkıyordu → `import`/`rapor` günlerce patlasa **Actions yeşil** kalırdı (`logs/` gitignore'da) | Hatalar tek yola (`_hata`) yazılıyor; `KRITIK_ADIMLAR = (import, rapor)` patlarsa `exit(1)` → dbdump+commit atlanır, yarım veri commit'lenmez |
| K-7 | "günlük hareket" alarmı `history_daily`'nin **en son** satırıyla karşılaştırıyordu; günlük koşumdan sonra bu BUGÜNÜN yarım kapanışı oluyor → fark ~0, alarm akşamları ölü | `date < bugun` şartı; ATR de aynı şekilde |
| K-8 | yfinance canlı sorguda piyasa kapalıyken bile "bugün" satırı döndürüyor; `_upsert` hiç silmediği için **kalıcı** oluyordu (2026-07-25/26 TRY=X hayalet barları) | `drop_unclosed_bar` YAZMA yoluna bağlandı **+ `drop_weekend_bars` eklendi** — bkz. (G) |
| K-5 | `test_karar._engel` fixture'ı üreticinin hiç yazmadığı `beklenen_gram_kazanc_pct`'yi elle koyuyordu → "SAT dalı çalışıyor" diyen test yeşil, üretimde dal ölü | Fixture üreticinin şemasına bağlandı + `test_engel_ozet_sozlesmesi_fixture_ile_ayni` sözleşme testi |
| LOW | 7 ölü config anahtarı (`kismi_oranlar`, `faz_duzeltmeli_taban`, `coverage_warn_pct`, `report.hour_local`, 2× purity, `backup:` bölümü); `grafik_ciz.CIKTI` config'i gölgeliyordu; `guven` hesaplanıp atılıyordu; `prim_series(only_valid)` ölü argümandı | Ölüler silindi, `CIKTI` config'e bağlandı, `guven TEXT` olarak kaydediliyor, argüman kaldırıldı |

`predictions` üretimde **0 satır** olduğu için `guven REAL → TEXT` şema
değişikliği migration gerektirmedi — bu pencere bir daha açılmayacak.

**Doğrulama:** 296 test (277 → +19). Her bulgu için düşebilen bir regresyon testi
var; `test_kapi_olculemez_karneden_sart_saglanmadi_DEMEZ` ve
`test_son_kapali_gun_bugunu_VARSAYILAN_olarak_disar` kilit testler.

### F) Denetimde ÇÜRÜTÜLEN iddia

"`chart.measure_edge` faz artefaktı hâlâ açık" diye ayrı bir bulgu yazmaya
hazırlanmıştım; ADR #007-E'de zaten ölçülüp backlog'a alınmış olduğunu görünce
**geri çektim.** Aynı şekilde `collector.py`/`supervisor.py`/`deploy/` "ölü kod"
gibi görünüyor ama PROJECT.md:39-42 onları Oracle Cloud senaryosu için bilinçli
tutuyor — **kasıtlı ve geçerli**, dokunulmadı.

### G) Hayalet bar: iddia ÖLÇÜLDÜ, yönü YANLIŞ çıktı

Dört farklı AI'a soruldu; dördü de aynı varsayımı tekrarladı: *"sıfır aralıklı
Pazar barı ATR'yi aşağı çekiyor."* **Ölçüm bunu çürüttü** (üretim dump'ı, ATR(14)):

| | `kur_atr` | `kur_rsi` |
|---|---:|---:|
| hayaletli | 0.076262 | 98.77 |
| temiz | 0.071157 | 98.95 |
| **fark** | **+%7.17 (YUKARI)** | −0.18p |

Kirleten Pazar barı değil: **Cumartesi barının aralığı 0.2226** — önceki 10 gerçek
barın ortalamasının (0.0404) **5.5 katı**. Sıfır aralıklı Pazar barı ihmal edilebilir.

**Etki değerlendirmesi:** `kur_atr` yalnız `ozellikler.feature_vector`'a giriyor ve
ADR #007-D gereği **oy vermiyor** (bağlam). `notify`'ın alarm ATR'si
`history_daily.gram_teorik`'ten geliyor, TRY=X'e hiç bakmıyor → "alarm yanılır"
korkusu yersizdi. Yani bugünkü zarar **düşük ama sıfır değil**.

**Karar:** yeni hayalet üretimi `drop_weekend_bars` ile kalıcı kapatıldı (ölçüm:
5401 tarihsel barın **0'ı** hafta sonu → meşru hafta sonu barı YOK, filtre güvenli).
`drop_unclosed_bar` tek başına yetmiyordu: Cumartesi yazılan bar Pazartesi
koşumunda geçmiş tarihlidir ve o filtreden geçer.

Bu, yeni bir emsal değil **var olan kuralın uygulanmasıdır**: `prim_history` zaten
her istatistik tabanında `indicative=0 AND weekend=0` filtreliyor; `ohlc_daily`'de
bu eksikti.

**Tekrar gözden geçir:**
- (a) **Gölge kol kararı** — B'deki açık iş. Ekim'e bırakıldı (2026-07-27 kararı).
  Verilmezse karne yine ölçüm üretmeyecek, ama artık bunu **söyleyecek**.
- (b) `beklenen_gram_kazanc_pct` üreticisi bağlanırsa C'deki dal ve testi kalkar.
- (c) Üretimdeki 2 hayalet TRY=X satırı hâlâ duruyor. **Zamanlama kritik:**
  `predictions` şu an 0 satır; kayıt başladıktan sonra silmek, o kayıtların
  özelliklerini yeniden üretilemez kılar (ADR #007-G "canlı = replay" ihlali).
  Temizlenecekse kayıt başlamadan temizlenmeli — veri silme Mert'in kararı.
- (d) `deploy/altin-backup.service` var olmayan `scripts/backup.sh`'ı çağırıyor —
  Oracle senaryosu aktive edilirse bu timer patlar.

---

## #007 — 2026-07-26 — Karar motoru: amaç fonksiyonu GRAM, taktik kol doğuştan kapalı

**Tetikleyen:** Mert: *"bu proje benim hiç işimi görmez, oldukça net şekilde
tahminlerini söylemesi lazım"* + *"her ay düzenli alıyorum, düşme riski varsa
satıp geri toplamak istiyorum — **yani elimdeki gramı artırmalıyım**."*

### A) Amaç fonksiyonu = terminal GRAM sayısı

Son cümle projeye eksik olan şeyi verdi. Ölçüt gram olunca TL enflasyonu
artefaktı ölür (`backtest._regime_stats_table` bunun için tabandan-fark sunmak
zorunda kalıyordu) ve her iddia yanlışlanabilir olur.

### B) En riskli varsayım ÖNCE ölçüldü — ve düştü

"Trade ederek gram artırılabilir" varsayımı, kod yazılmadan ölçüldü
(2561 gün, 2016-01-04→2026-07-24, örtüşmeyen pencere, tüm fazlar, TP.TRY.MT03
mevduat carry'si net dahil). **"SAT → mevduatta bekle → geri al" işleminin gram
kazancı:**

| Ufuk | N | Ortalama | SAT kazanır | Maliyet sonrası | En kötü |
|---|---:|---:|---:|---:|---:|
| 1 hafta | 512 | −0.47% | %42 | %24 | −24.0% |
| 1 ay | 121 | **−1.99%** | %36 | %28 | **−36.2%** |
| 3 ay | 40 | −6.14% | %22 | %19 | −49.4% |

Alt dönem: 2016-19 −1.35% · 2020-22 −2.84% · 2023-26 −1.98% → **her rejimde aynı
işaret, yapısal** (TL mevduat faizi ≈ TL değer kaybı ≈ gram TL sürüklenmesi).

Gidiş-dönüş maliyeti (`calculators.instrument_net`): banka_hesap **%1.20**,
altins1 **%0.40**, fiziki **%3.00**. → Bir SAT sinyalinin 1 ay ufkunda tabanı
**+3.18 puan** yenmesi gerekiyor. Taranan adayların en iyisi +1.4p (t≈1.4).

**Sonuç: satmak ortalamada gram KAYBETTİRİR ve bunu tersine çeviren sinyal henüz
ölçülmedi.**

### C) Karar: iki kol, biri doğuştan kapalı

- **ÇEKİRDEK** (aylık alımı zamanlar) — **açık, birincil.** Gidiş-dönüş makası
  ödemez → eşiği %1.20 daha düşük. Kademeler bilerek DAR (1.25× / 0.75×): kapı
  değişkeninin (reel net mevduat) ölçülen kenarı t≈1.4, yani en iyi aday ama
  kanıt değil; 2x/0.5x agresiflik bu kanıtla savunulamaz. Kol alımı asla KESMEZ.
- **TAKTİK** (sat/geri al) — **doğuştan KAPALI.** `karar.taktik.aktif: false`.
  Açılma şartı önceden config'e yazıldı ve gevşetilmez: canlı karnede ≥30
  çözülmüş tahmin **ve** gram etkisi > 0 **ve** isabet farkı > +10p.

Bu, prim z-skoru kapısının (`signals.zscore_dry_run`) birebir aynısıdır. Sistem
"yapamam" demez; **"henüz hakkını kazanmadım, şu sayı görününce söyleyeceğim"**
der. Kural `tests/test_karar.py::test_kapi_kapaliyken_en_guclu_sinyal_bile_tut`
ile kilitlendi.

### D) Ağırlık öğrenme REDDEDİLDİ

1 ay ufkunda 121 örtüşmeyen pencere, ~5 bağımsız makro epizot var. 7 bileşen ×
3 ufuk = 21 ağırlığı "kayıt biriktikçe yeniden kestirmek" ders kitabı
aşırı-uydurmadır; üstelik geri besleme sistemin kendi gürültüsünü onaylamasına
yol açar. Yerine: **tek kapı değişkeni + sabit önceden-kayıtlı eşikler**; diğer
6 gösterge bağlam olarak gösterilir, **oy vermez**.

### E) Yan bulgu: `chart.measure_edge`'de faz artefaktı

Taban `range(len(closes))` ile 0. fazdan başlıyor, sinyal kümesi başka fazdan.
Ölçüldü — yalnız faz seçiminden gelen taban yayılımı:

| | h=21 | h=63 | h=126 |
|---|---:|---:|---:|
| ons USD | 0.91p | 2.64p | 7.46p |
| gram TL | 1.18p | 3.23p | 11.58p |

`chart.dogrulama.min_anlamli_fark_puan = 1.0` → h≥63'te faz gürültüsü eşiğin
3-11 katı. **`reports/grafik_dogrulama.md`'nin uzun ufuk "zayıf kanıt" bulguları
faz artefaktından ayırt edilemez.** Yeni motor bu hatayı miras almıyor:
`gram.phase_matched_baseline` tüm fazlar üzerinden ölçer ve yayılımı raporlar.

### F) Tahmin kaydı DEĞİŞTİRİLEMEZ (Faz C, aynı gün)

Verilen her hüküm `predictions`'a yazılır ve `trg_predictions_immutable`
trigger'ı `hukum/skor/guven/ozellikler_json/asof_date/esik_pct/kapi_acik/
horizon_days/target_date/kol` kolonlarında UPDATE'i ABORT ediyor.

**Neden şema düzeyinde:** karneyi güzelleştirmek için geçmiş bir tahmini
"düzeltmek" kaçınılmaz bir ayartıdır ("şu tahmin bozuktu, elle düzelteyim").
Disiplinle değil, imkânsızlıkla çözülür.

Üç ek koruma:
- **Giriş fiyatı AYRI tabloda** (`prediction_entries`): hüküm asof=T-1'de
  verilir, giriş T'nin kapanışıdır ve o an bilinmez. Aynı satıra yazmak
  look-ahead olurdu.
- **Giriş ve çıkış İKİSİ de 3 işlem günü ortalaması.** Yalnız çıkışı ortalamak,
  yukarı sürüklenen bir seride sistematik TUT yanlılığı yaratır.
- **Kaçınma yasak:** her asof tam olarak bir hüküm üretir; "emin değilim" diye
  atlamak karneyi seçerek temizlemenin kapısıdır.

`dbdump._TABLES`'a üç tablo da eklendi. `predictions.id` — `ticks.id`'nin
aksine — dump'a GİRER: `prediction_entries/outcomes` ona referans veriyor,
hariç tutulsaydı restore'da bağlar sessizce kopardı.

### G) Tek özellik giriş noktası (Faz D, aynı gün)

`src/ozellikler.py` `feature_vector(cfg, con, asof_date)` — canlı üretim ve
tarihsel replay **aynı fonksiyonu** çağırır. Look-ahead artık disiplinle değil
**yapısal olarak** engelleniyor: `asof`'tan sonraki hiçbir satırı okumayan tek
kod yolu budur. `tahmin.kaydet` ve `karar.build_karar` ikisi de buraya bağlandı.

41 özellik: momentum (21/63/126/252g), 200GMA konumu, gerçekleşen oynaklık,
Donchian 20/55, Wilder ATR + RSI (ons & kur gerçek OHLC'den; gram yalnız
kapanıştan — `db.py` kuralı), ons/kur bacağı payı, makro (mevduat, politika
faizi, enflasyon beklentisi, reel net mevduat).

**Yayın gecikmesi bir look-ahead'i kapattı.** `evds_daily.date` dönem başıdır;
eski yol (`evds_job.context`) gecikme uygulamıyordu. Aynı gün ölçülen fark:
reel net mevduat **%12.7 → %13.1**. Eski sayı hafifçe kontamineydi.

Ayrıca `feature_vector` TÜFE'ye **düşmez** (`evds_job.context` düşüyor). Sebep:
TÜFE serisi 7 aydır bayat; sessiz yedeğe düşme replay'de canlıdan farklı
davranırdı — kesişim kuralının ihlali olurdu.

**Test kanıtı:** `test_look_ahead_gelecek_silinince_ayni_sonuc` — `asof` sonrası
tüm satırlar silinince birebir aynı sözlük dönmeli. Testin gerçekten
düşebildiği, `asof` filtresi kasten kaldırılarak doğrulandı (3 test düştü,
`gram_getiri_6ay` 16.3 → 11531 sızıntısını isim isim gösterdi).

**Gözlem, kurala DÖNÜŞTÜRÜLMEDİ:** kur oynaklığı bugün %1.42 (son 60 günün 59'u
artı) — 10 yılın en sıkı sürünen kur rejimi (2018 %43.0 · 2021 %23.9 · 2023
%15.1). Sürünen kur + yüksek mevduat faizi, "sat ve TL'de otur"un kâğıt üstünde
en cazip göründüğü rejimdir; oysa en kötü iki SAT ayı (gram −33%, −36%) tam da
sürünmenin bittiği aylardır. Ölçülmemiş bir sinyali hükme sokmak bu ADR'nin
yasakladığı şey olduğu için yalnız özellik olarak kayıtta.

### H) Aday taraması: 14 aday, HİÇBİRİ eşiği geçemedi (Faz E, aynı gün)

`src/tahmin_backfill.py` — 2017-01-19 → 2026-07-24, **458 haftalık asof**,
özellikler canlıyla aynı yoldan (`ozellikler.feature_vector`), örtüşmeyen
pencere, tüm fazlar. Aşılması gereken eşik: **+3.18 puan**.

| Aday | N | Tabana fark | t |
|---|---:|---:|---:|
| kur oynaklık > %25 (şok) | 6 ⚠️ | +2.85p | +1.01 |
| reel_mevduat > %10 | 22 ⚠️ | +1.34p | +1.03 |
| gram 12ay momentum > %60 | 47 | +0.45p | +0.55 |
| **kur oynaklık < %5 (sürünme)** | 30 | **−0.47p** | −0.49 |
| gram 200GMA üstü %15+ | 55 | −0.78p | −0.89 |
| reel_mevduat < 0 | 34 | −1.06p | −0.80 |

**Hiçbiri geçmedi.** Bu güçlü ve kalıcı bir sonuçtur: eşikler bu veriye
bakılarak seçildiği için ölçüm örneklem-**içi**dir, yani bir ÜST SINIR. Örneklem
içinde bile aşılamayan eşik, örneklem dışında hiç aşılmaz. Taktik kol kapalı
kalır — bu bir başarısızlık değil, **sonuçtur**.

**Bu modül karne ÜRETMEZ.** 10.5 yıllık replay'e "işte karnem" demek cazipti ama
sahte olurdu. Rapor başında bunu bağırarak yazan bir uyarı var ve testle
korunuyor (`test_rapor_karne_olmadigini_bagirarak_soyler`).

**Sürünen kur tuzağı artık spekülasyon değil, ölçüm:** G'de "kurala
dönüştürülmedi" diye not düşülen gözlem tarandı — sürünen kur rejiminde (bugünkü
rejim, %1.42) satmak, zaten negatif olan tabandan **daha da kötü** (−0.47p).
Yine de t=−0.49, yani **kural yapılmadı**; yalnız TUT'un gerekçesini
güçlendiren bir bağlam.

**Tekrar gözden geçir:** (a) taktik kapısı açılırsa veya 30 tahmin çözülüp şart
sağlanmazsa — o zaman "trade kolu kalıcı kapalı" ADR'si yazılır; (b) ALTINS1'e
geçilirse eşik %1.20 → %0.40 düşer, taktik kol yeniden değerlendirilir;
(c) `chart.validate` faz düzeltmesiyle yeniden koşulmalı.

---

## #006 — 2026-07-25 — Backlog kapatma: FRED yedeği, z-skor kuru provası, çeyrek primi, tek kaynak eşik

Dört açık iş sırayla kapatıldı. Her biri önce **ölçüldü**, sonra karar verildi.

### A) FRED 18 gündür ölü → DXY'ye yedek, reel faize YEDEK YOK

**Ölçüm:** FRED (`fredgraph.csv`) 2026-07-07'den beri üretimde **hiç** yanıt vermedi
(tüm raporlarda "veri yok"). 2026-07-25'te yerelden de doğrulandı: hem `fredgraph.csv`
hem `data/*.txt` zaman aşımına düşüyor, User-Agent'tan bağımsız → engelleme değil,
endpoint ölü. Panel 7 göstergenin **5'iyle** karar veriyordu.

**Karar:**
- **DXY:** yfinance `DX-Y.NYB` yedeği (config'de zaten tanımlıydı ama **hiç
  çağrılmıyordu** — ölü ayar). İkisi de dolar gücünü ölçer ve panel yalnız ~1 aylık
  yüzde değişimi kullandığı için sepet farkı yön bilgisini bozmaz. Kullanılan kaynak
  raporda yazılır — sessiz ikame yok. Panel **5/7 → 6/7**.
- **Reel faiz:** yedek KOYULMADI. `^TNX` nominal getiridir, TIPS reel getirisi değil;
  nominali "reel faiz" diye sunmak ölçümü sahtelemek olurdu (Faz 3/6 kültürü).
  Gösterge dürüstçe "veri yok" kalır ve paydadan düşer.
- **İsraf:** eski ayar (60 sn × 3 deneme × 2 seri) her rapor çalışmasında **6 dakikaya
  kadar** boşuna bekletiyordu. 15 sn × 2 denemeye çekildi → ölçülen 360s → 66s.

### B) Z-skor kuru provası (dry-run) — Eylül'ü riskten arındırır

**Sorun:** 60 günlük kapı ~Eylül'de açılacak ve `z > 2` bildirimi o ana dek **hiç**
ateşlenmemiş olacak. Kalibrasyonsuz açılırsa beklenmedik sıklıkta alarm günlük tavanı
(6) doldurup diğer bildirimleri bastırabilir.

**Karar:** `signals.zscore_dry_run()` — kapıyı yok sayarak z'yi hesaplar, **bildirim
göndermez**, `data/zskor_prova.jsonl`'a günde 1 satır yazar (daily_job adım 3c).

**Prova ilk günden değerli bir şey ölçtü:** kapı GÜN sayıyor (Faz 7) ama z hâlâ TÜM
KAYITLAR üzerinden hesaplanıyor. İki taban karşılaştırıldı:

| Taban | z | std |
|---|---|---|
| Kayıt (mevcut) | +0.92 | 0.118 |
| Gün (kapıyla tutarlı) | **+1.36** | 0.081 |

Gün tabanında std daha küçük (gün içi gürültü ortalanıyor) → aynı sapma **daha büyük z**
üretiyor. Doğru tabana geçilirse eşik **daha sık** tetiklenecek. Kapı açılmadan bilmek
tam olarak provanın amacıydı. Hangi tabanın kullanılacağı kapı açılmadan önce, birikmiş
prova verisine bakılarak kararlaştırılacak.

### C) Çeyrek primi kuralı sessizce ölüydü

**Ölçüm:** `config.yaml`'da `quarter_z` eşiği, `notify.evaluate_thresholds`'ta kuralı
vardı — ama `build_context` her seferinde `"quarter_z": None` döndürüyordu
("şimdilik pas" yorumu). Veri mevcuttu (238 kayıt, 16 gün, -1.51%…+2.00%). Yani
**var sanılan bir alarm hiç ateşlenemiyordu** (LESSONS L-002).

**Karar:** `quarter_z` prim z ile **aynı 60 günlük kapıya** bağlandı; kapı açılınca
kendiliğinden hesaplanır. **Sezon düzeltmesi YOK** ve bu açıkça yazıldı: ziynet
talebinde yıllık örüntü olabilir ama düzeltme yıllar süren arşiv ister; düz z sezonu
"anomali" sanabilir. Sınır gizlenmiyor.

Denetimde **yarım bağlama** yakalandı: `quarter_z` yalnız alarm yoluna (`notify`)
bağlanmıştı; rapor onu göstermiyordu ve kuru prova onu ölçmüyordu. Yani kapı
açıldığında "çeyrek |z| > 2" alarmı gelecek ama tetikleyen sayı raporda hiç
görünmeyecekti — düzeltilen hatanın aynısının yeni bir kopyası. İkisi de kapatıldı:
rapor artık çeyrek z'sini yazıyor ve prova çeyreği de ölçüyor
(ilk ölçüm: çeyrek kayıt z=−0.85, gün z=−1.38).

### D) İkiz eşik mantığı — tek kaynağa indirildi

**Ölçüm:** İki kopya **zaten ayrışmıştı**. Üretim (`notify.evaluate_thresholds`,
Actions çağırıyor) **5 kural** uyguluyordu; CLI (`signals.evaluate_alerts`) yalnız
**3'ünü** biliyordu — `makas` ve `ceyrek_prim` eksikti.

**Karar:** `signals.evaluate_alerts` artık `notify`'ı çağırıp çıktıyı CLI biçimine
dönüştüren ince bir sarmalayıcı. Eşik değiştirmek isteyen **tek yere** bakar.
Ayrışmanın tekrarını engelleyen testler yazıldı.

**Doğrulama:** 170/170 test (153 → +17). DXY canlı ölçüldü (`+0.02% · kaynak DX-Y.NYB`),
kuru prova gerçek DB'de çalıştırıldı, `quarter_z` kapı açılınca hesaplanıyor (eşik
geçici düşürülerek doğrulandı), CLI eşik çıktısı üretimle birebir aynı kural kümesini
veriyor.

**Tekrar gözden geçir:** FRED geri gelirse DXY otomatik olarak FRED'e döner (yedek
yalnız FRED boşken devreye girer). Kapı açılmadan önce prova verisi okunup z tabanı
(kayıt mı gün mü) kararlaştırılmalı.

---

## #005 — 2026-07-24 — "Kesinti" metriği yanlış alarm üretiyordu: prim boşluğu ≠ çekim kesintisi

**Bağlam:** "Toplama otomasyonu düzenli kesintiye uğruyor, kapsama %62-81'e
düşüyor, arşiv sağlığı %16-17, en uzun kesinti 545 dk" iddiası araştırıldı.
Ölçüm sonucu iddianın TAMAMI yanlış çıktı, ama kaynağında gerçek bir metrik
kusuru bulundu:

- **Toplama hızı sabit:** 07-08'den beri medyan **13 kayıt/gün** (min 10, max 17).
  Hiçbir bozulma/trend yok — "düzenli kesinti" yok.
- **%16-17 ve %1-2 rakamları eski:** 07-21'deki `7d1171f` kalibrasyon commit'inden
  ÖNCEki raporlardan. O tarihe kadar beklenen kayıt nominal cron'a göre (96/gün)
  hesaplanıyordu; gerçek ritim ~90 dk olduğu için oran yapay olarak düşük çıkıyordu.
  Kalibrasyondan sonra aynı toplama hızı %62-81 olarak görünüyor. Metrik düzeldi,
  sistem zaten aynıydı.
- **545/457 dk "kesinti" ARIZA DEĞİL:** O pencerelerde Actions tam zamanında
  çalışmıştı (çekim boşluğu 217/216 dk, tolerans 270 dk altında). Boşluk,
  truncgil'in boş dönmesinden — CSV satırı var ama `gram_has_sell` boş, prim
  hesaplanamıyor. Geçersizler günün her saatine dağılmış (sistematik saat deseni
  YOK) → geçici hatalar → DECISIONS #003'teki kaynak-retry tam da bunu hedefliyor.
- **Z-skor takılı değil:** 60 gün eşiği, sayaç düzenli ilerliyor (07-22'de 14 →
  07-23'te 15 → 07-24'te 16). Takvim meselesi, arıza değil; ~Eylül'de olgunlaşır.

**Gerçek kusur:** Rapor iki FARKLI olguyu neredeyse eşanlamlı kelimelerle
yazıyordu — "en uzun kesinti" (prim_history boşluğu, kaynak boşsa da büyür) ve
"en uzun boşluk" (Actions çekim boşluğu). Üstelik uyarı satırı prim boşluğuna
bakıp "kesinti" diyordu → altyapı arızası sanılıyordu. Bu belirsizlik bu
araştırmayı tetikleyen yanlış alarmın ta kendisi.

**Karar:** `report.classify_gap()` saf fonksiyonu eklendi (testli): prim boşluğu
toleransı aşsa bile çekim boşluğu sağlıklıysa "kaynak kalitesi" (ℹ️) der,
"Actions kontrol edilmeli" (⚠️) DEMEZ. Etiketler netleştirildi: "en uzun **prim**
boşluğu" / "en uzun **çekim** boşluğu". Çekim de durmuşsa gerçek arıza uyarısı
korunur; arşiv sağlığı okunamazsa güvenli tarafta kalıp uyarır.

**Neden:** Sistemde düzeltilecek bir arıza YOK; düzeltilecek olan yanıltıcı
metrikti. Yanlış alarm, alarm yorgunluğu ve boşa araştırma maliyeti üretir.
Değişiklik küçük, saf, testli ve geri alınabilir.

**Tekrar gözden geçir:** Kaynak-retry (#003) birkaç gün çalıştıktan sonra
geçersiz kayıt oranı ölçülsün; %7'den belirgin düşmezse truncgil için yedek
kaynak (fallback) gündeme gelir.

---

## #004 — 2026-07-24 — history_daily donmuş bulundu (17 gün) → ATR/günlük-hareket alarmları yanlış hesaplıyordu

**Bağlam:** Mert "botun çıktıları mantıklı mı" diye sordu. Telegram export'undaki 7
"hareket > 2.0×ATR" alarmının HEPSİ birebir aynı `ATR(75)` yazıyordu (08-21 Tem
arası). DB'de doğrulandı: `history_daily` tablosunun son satırı **2026-07-07**
— 17 gündür donmuş. Kök neden: bu tablo YALNIZCA `src/history.py::build_history_daily`
(elle çalıştırılan tek seferlik backfill script'i) tarafından yazılıyordu;
`daily_job.py`'nin otomatik pipeline'ında hiç çağrılmıyordu. Sonuç: notify.py'nin
ATR(14) ve "günlük hareket" (dünkü kapanışa göre) hesapları 17 gündür sabit/yanlış
referanstan besleniyordu — alarmların KENDİSİ (soğuma/tavan/format) doğru
çalışıyordu ama İÇERİĞİ (eşik değeri) yanlıştı.

**Seçenekler:**
- A) Dokunma, bir dahaki elle `history build` çalıştırmayı bekle → aynı hata tekrarlar
- B) `history_daily`'yi `daily_job.py`'ye bağla (artımlı, son ~45 gün, idempotent) →
  kendi kendini onarır, bir daha donmaz

**Karar:** B. `history.update_recent(cfg, days=45)` eklendi, `daily_job.py`'de
EVDS adımından sonra çağrılıyor (EVDS günlük USD kuru gerektiği için). Ayrıca
`_yf_ons_daily`'deki sabit `min_days=200` sanity-check'i parametrik yapıldı —
kısa pencereli artımlı çağrı bu eşiği hiç geçemiyordu (kendi içinde ikinci bir
gizli hata). `build_history_daily`'nin varsayılanı (200) korunarak geriye dönük
uyumluluk sağlandı.

**Neden:** En basit, kendi kendini onaran çözüm; dış bağımlılık yok, mevcut
günlük pipeline'a ince bir adım. Elle hatırlamaya güvenmek [[ölçüm kültürü]]ne
aykırı — otomatik olmalı.

**Doğrulama:** 148/148 test geçti. Canlı DB'de çalıştırıldı: `history_daily`
07-07→07-24 arası 12 eksik günü doldurdu, ATR 75(donuk)→80.5(taze) değişti.
`data/altin.sql` dump'ı yalnız history_daily satırlarını içeriyor (diff kontrol
edildi — başka tabloya dokunmadı).

**Tekrar gözden geçir:** `update_recent` günlerce başarısız kalırsa (log'da
"history hata") kaynak (yfinance/EVDS) tarafında kalıcı bir sorun var demektir.

---

## #003 — 2026-07-24 — Veri kapsaması: platform kısıtını kabul et, veri kalitesini iyileştir

**Bağlam:** Raporlar "kapsama %62" gösteriyordu. Ölçüm (17 gün, 231 kayıt):
GitHub Actions `*/15` cron'unu gerçekte medyan ~94 dk'da çalıştırıyor (6 kat seyrek) —
throttling. Ayrı olarak kayıtların ~%7'si truncgil transient hatasından geçersiz
(gram/çeyrek boş; yfinance/ons hep dolu).

**Seçenekler:**
- A) Dış cron servisi → `workflow_dispatch` ile ~15 dk garanti → zamanlamayı düzeltir
  AMA dış bağımlılık + GitHub PAT'i 3. tarafta (güvenlik yüzeyi); "ayrı sunucu/servis
  yok" kısıtına aykırı
- B) Tur-içi çoklu örnekleme → kayıt sayısını şişirir ama kapsama metriğini
  anlamsızlaştırır (kümelenmiş örnek; 90 dk kör nokta durur) — metriği kandırır
- C) Platform kısıtını KABUL et (~90 dk kişisel monitör için yeterli — YAGNI) +
  gerçek ücretsiz kazanç olan VERİ KALİTESİNİ iyileştir: kaynak retry

**Karar:** C. GitHub cron throttling ücretsiz düzeltilemez ve ~90 dk bu kullanım için
yeterli. `archive_fetch`'e kaynak-retry eklendi (`sources.fetch_retries=3`,
`fetch_retry_backoff_s=4`) → %7 geçersiz kayıt düşer. Kapsama metriği dürüst
bırakıldı (şişirilmedi). Dış altyapı reddedildi.

**Neden:** Mert'in kısıtı ücretsiz + ayrı sunucu yok + basit. Retry hepsini karşılar;
dış cron+PAT karşılamaz. Metriği şişirmek [[ölçüm kültürü]]ne aykırı.

**Tekrar gözden geçir:** Sub-90-dk anomali tespiti kanıtlanmış ihtiyaç olursa
(gün-içi sert hareketler kaçırılıyorsa) dış tetikleyici (A) yeniden masada.

---

## #002 — 2026-07-24 — Usta sistemi proje köküne + tüm IDE köprüleri

**Bağlam:** Claude Code aboneliği bitince altın projesi Codex, Antigravity, GLM,
Kiro, VSCode gibi farklı araç+modellerle geliştirilecek. Usta sistemi bir alt
klasördeydi (`Proje Yardımcısı/`) — hiçbir IDE alt klasördeki kural dosyasını
otomatik okumaz, sistem atıldı.

**Seçenekler:**
- A) Alt klasörde tut, kökten köprü ver → kırılgan; relative path'ler bozulur,
  Kiro steering redirect'i güvenilmez
- B) Sistemi proje KÖKÜNE taşı (`yeni-proje.sh`'in kendi tasarımı) → her araç
  kökten okur
- C) Her araç için elle ayrı config → bakım zor, drift riski

**Karar:** B. Kök kanonik `AGENTS.md` + `ai/` hafıza; `CLAUDE.md`, `GEMINI.md`,
`.github/copilot-instructions.md` ve `.kiro/steering/usta.md` yalnızca AGENTS.md'ye
işaret eden köprüler. Codex/Cursor/GLM: AGENTS.md (GLM Claude-uyumlu istemcide
CLAUDE.md); Kiro: `.kiro/steering`; VSCode: copilot-instructions.

**Neden:** Alt klasör = atıl sistem. Kök yerleşim, şablonun kendi script'inin
yaptığı şey ve tek gerçekten evrensel konum. Düz markdown → araç kilidi yok.

**Tekrar gözden geçir:** Bir araç AGENTS.md/steering desteğini bırakır veya yeni
bir araç farklı bir konvansiyon dayatırsa köprü ekle/güncelle.

> **Güncelleme (2026-07-25):** Kiro köprüsü (`.kiro/steering/usta.md`) kullanıcı
> kararıyla **kaldırıldı** — Kiro pratikte az kullanılıyor, diğer köprüler yeterli.
> Kararın özü (kök kanonik + ince köprüler) değişmedi; yalnız köprü listesinden bir
> araç çıktı. Gerekirse AGENTS.md'ye yönlendiren 3 satırlık dosyayla geri eklenir.

---

## #001 — 2026-07-23 — Taşınabilirlik için AGENTS.md standardı + düz markdown hafıza

**Bağlam:** Claude Code aboneliği bitince Cursor, Antigravity, VS Code gibi
farklı araçlara geçilecek. Usta sistemi her araçta aynı şekilde çalışmalı.

**Seçenekler:**
- A) Araca özel özellikler (.claude/commands, .cursorrules...) → güçlü ama her araçta yeniden kurulum gerekir
- B) Tek AGENTS.md + düz markdown hafıza dosyaları → her uyumlu araç okur, kilitlenme yok
- C) Fine-tuning / özel model → pahalı ve gereksiz; sorun davranış+bağlam sorunu, bilgi sorunu değil

**Karar:** B. AGENTS.md kanonik dosya; CLAUDE.md, GEMINI.md ve
copilot-instructions.md yalnızca ona işaret eden köprüler. Komutlar araç
özelliği değil, AGENTS.md içinde "sözleşme" olarak tanımlı.

**Neden:** AGENTS.md araçlar arası fiili standart (Claude Code, Cursor,
Antigravity, Copilot, Codex destekliyor). Düz markdown hiçbir araca bağımlı
değil; git ile taşınır, her yerde okunur.

**Tekrar gözden geçir:** Ana kullanılan araç AGENTS.md desteğini bırakırsa
veya araca özel bir özellik (ör. gerçek slash komutları) ciddi verim farkı
yaratmaya başlarsa.

---

<!-- Yeni karar şablonu:

## #NNN — YYYY-MM-DD — Kısa başlık

**Bağlam:** Hangi sorun/ihtiyaç bu kararı doğurdu?

**Seçenekler:**
- A) ... → artı/eksi
- B) ... → artı/eksi

**Karar:** Seçilen şey.

**Neden:** Hangi kısıta/hedefe dayanarak?

**Tekrar gözden geçir:** Hangi koşul oluşursa bu karar masaya geri gelir?
-->
