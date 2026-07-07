# Türkiye Altın Takip & Strateji Projesi — Tasarım Rehberi

> Tarih: 2026-07-07. Vergi oranları ve API koşulları değişebilir; üretime almadan önce güncel kaynaktan doğrulayın.

---

## 1. Fiyat ve Piyasa Verisi Katmanı

### 1.1 Çekirdek formül ve türetilen sinyaller

```
Teorik gram (TL) = (XAU/USD ÷ 31.1035) × USD/TRY          ← has altın (24 ayar) bazında
Prim %          = (Piyasa gram − Teorik gram) / Teorik gram × 100
```

Kapalıçarşı "Has Altın" 995/1000 saflıkla kote edilir; karşılaştırma yaparken saflık düzeltmesi yap
(995 fiyatını 0.995'e bölerek 1000 bazına getir), yoksa kalıcı ~%0.5'lik sahte "iskonto" görürsün.

**Ziynet altınların has içeriği (prim hesabının temeli):**

| Ürün | Brüt gram | Ayar (milyem) | Has içerik |
|---|---|---|---|
| Çeyrek | 1.804 g | 22 (916.6) | ≈ 1.654 g |
| Yarım | 3.608 g | 22 | ≈ 3.307 g |
| Tam / Cumhuriyet | 7.216 g | 22 | ≈ 6.615 g |
| 22 ayar bilezik | değişken | 916 | brüt × 0.916 |

```
Çeyrek primi % = Çeyrek satış fiyatı / (1.654 × has gram fiyatı) − 1
```

Bu prim, düğün sezonu / bayram öncesi fiziki talebin en net göstergesidir. Aynı mantık tam ve
Cumhuriyet altını için de kurulur; Cumhuriyet altınında ayrıca "darp yılı / koleksiyon" gürültüsü olur.

**Makas (spread) sinyali:** `(satış − alış) / orta fiyat`. Üç kanalda ayrı izle: Kapalıçarşı has,
banka gram hesabı, kuyumcu perakende. Makasın tarihsel yüzdelik dilimini (p50/p90/p99) tut;
p90 üstüne çıkması panik/talep şoku sinyalidir (ör. deprem, seçim gecesi, kur şoku günleri).

**BIST enstrümanları:** Darphane Altın Sertifikası (ALTINS1), altın BYF'leri (ör. GLDTR/ZGOLD),
altın fonları. `Sertifika fiyatı / (içerdiği has gram × spot has fiyat)` oranı ayrı bir prim/iskonto
serisidir — spot ile sertifika arasındaki makas açıldığında arbitraj/likidite sinyali üretir.

### 1.2 Veri kaynakları karşılaştırması

| Kaynak | Kapsam | Maliyet | Gecikme / Güncelleme | Güvenilirlik & Notlar |
|---|---|---|---|---|
| **TCMB EVDS** | Resmi kur, BIST altın serileri, faiz, TÜFE, beklenti anketi, KKM | Ücretsiz (API key) | Günlük / gün sonu — canlı DEĞİL | En güvenilir tarihsel/makro kaynak. Nisan 2024'ten beri key URL'de değil HTTP header'da gönderiliyor. Python: `evds` paketi. |
| **Truncgil Finans** (`finans.truncgil.com/today.json`, v2/v3) | Serbest piyasa altın + döviz, TR odaklı | Ücretsiz | Dakikalar mertebesi | SLA/rate-limit garantisi yok; hobi/MVP için iyi, üretimde tek başına güvenme. v3 TCMB yerine serbest piyasa verisi kullanıyor. |
| **AltinAPI / Hasfiyat** | Kapalıçarşı (Harem Altın ile aynı veri), 67 sembol, REST + WebSocket | Ücretli | <1 sn (WebSocket) | Canlı Kapalıçarşı için en ciddi seçenek. Harem'in kendi resmî public API'si yok. RapidAPI'de "Harem Altın Live" benzeri üçüncü parti seçenekler de var. |
| **CollectAPI (economy)** | Altın + döviz + borsa, TR odaklı | Freemium (düşük ücretsiz kota) | Dakikalar | Kota aşımı ve fiyatlandırma değişkenliğine dikkat. |
| **GoldAPI.io / Metals-API / MetalpriceAPI** | XAU/USD global spot + tarihsel | Freemium, ücretsiz kotalar düşük (aylık ~100 istek mertebesi) | Gerçek zamanlıya yakın | Kapalıçarşı verisi YOK; sadece ons bacağı için. |
| **Yahoo Finance** (`GC=F`, `XAUUSD=X`, `TRY=X`, `yfinance`) | Ons + kur, uzun tarihsel | Ücretsiz | 1-15 dk gecikmeli | Resmî API değil, kırılabilir; backtest tarihsel verisi için pratik. |
| **BDDK / SPDR / FRED** | KKM bakiye (haftalık), GLD tonaj (günlük CSV), ABD reel faiz (DFII10) | Ücretsiz | Günlük/haftalık | Makro katman için. |

**Önerilen mimari:** iki katman —
1. **Canlı katman:** Kapalıçarşı (AltinAPI WebSocket veya 30-60 sn REST poll) + ons + kur → prim/makas hesabı.
2. **Tarihsel katman:** EVDS + yfinance günlük seriler → backtest ve rejim analizi.

Kritik: **1. günden itibaren kendi tick/dakika arşivini biriktir** (SQLite/Postgres, 1 dk OHLC yeter).
Kapalıçarşı prim ve makasın tarihsel verisi hiçbir yerde hazır satılmıyor — kendi arşivin projenin
en değerli ve kopyalanamaz varlığı olur.

### 1.3 Piyasa takvimi ve hafta sonu problemi

Üç bacağın çalışma saatleri farklıdır ve prim hesabı ancak **üçü de taze iken** sinyal kalitesindedir:

| Bacak | Açık olduğu zaman | Hafta sonu davranışı |
|---|---|---|
| Ons (XAU/USD OTC) | Pazar 18:00 ET → Cuma 17:00 ET (TR saatiyle Pzt ~01:00 → Cmt ~00:00-01:00), her gün ~1 saat ara (17:00-18:00 ET) | **Donuk** — Cuma kapanışı geçerli |
| USD/TRY | Bankalararası hafta içi; TCMB resmi kur günlük | Resmi kur donuk; bazı serbest/offshore kotasyonlar hafta sonu da akar (güvenilirliği düşük) |
| Kapalıçarşı serbest piyasa | Fiilen 7/24 kotasyon (Harem vb. online) | **Akmaya devam eder** |

**Tasarım — piyasa durum makinesi:** her veri bacağına durum etiketi ver:
`FRESH` (yaş < eşik) / `STALE` / `CLOSED_WEEKEND` / `CLOSED_HOLIDAY`.

Kurallar:
1. Prim/makas **sinyali ve bildirimi yalnızca üç bacak da FRESH iken** üretilir. Herhangi biri
   donuksa prim yine hesaplanır ama `"indicative": true` etiketiyle — anomali bildirimleri bastırılır.
   (Aksi halde her cumartesi "prim %2 açıldı!" sahte alarmı üretirsin.)
2. Hafta sonu sapması çöp değil, **ayrı bir sinyaldir**: hafta sonu Kapalıçarşı fiyatı, piyasanın
   pazartesi açılış beklentisini içerir. `haftasonu_beklenti = haftasonu_gram / donmuş_teorik − 1`
   serisini ayrı sakla ve pazartesi gerçekleşmeyle karşılaştır — "piyasa pazartesi %X'lik kur/ons
   hareketi fiyatlıyor" çıktısı üret.
3. Pazartesi açılışta **mutabakat (reconciliation) job'ı**: hafta sonu prim noktalarını retroaktif
   olarak `weekend=true` etiketle; backtest ve z-skor hesaplarına bu noktaları **sokma** (yoksa prim
   dağılımın şişer ve gerçek anomali eşiğin bozulur).
4. **Tatil takvimleri:** ABD tatilleri (ons kapalı/erken kapanış), TR resmi tatiller + dini bayramlar
   (fiziki piyasa kapalı ama online kotasyon sürer → likidite düşük, makas doğal olarak genişler —
   makas bildirimine tatil düzeltmesi koy). Takvimi koda gömme; yıllık güncellenen config dosyası yap
   (dini bayramlar her yıl kayar).
5. Günlük ons arasında (17:00-18:00 ET) ve TR gece saatlerinde likidite düşüktür — `STALE` eşiğini
   bacağa göre ayarla (ons: 15 dk, Kapalıçarşı gündüz: 5 dk, gece: 60 dk).

### 1.4 Veri kullanım hakları (kişisel araç ≠ ticari ürün)

| Kaynak | Kişisel/prototip | Ticari ürün |
|---|---|---|
| **Truncgil** | Sorun yok | Yayımlanmış ToS/lisans metni yok → **yazılı izin almadan kullanma**. E-posta ile ticari kullanım izni iste; alamazsan üretimde kullanma. |
| **yfinance / Yahoo** | Gri alan (resmî API değil) | Yahoo ToS ticari kullanımı yasaklar → **üründe kullanma**. Backtest için bile üretim hattına sokma. |
| **TCMB EVDS** | Serbest | Genel olarak **kaynak göstererek** kullanılabilir (kamu verisi); yine de EVDS kullanım koşulları sayfasını kontrol et ve "Kaynak: TCMB EVDS" ibaresini ürüne koy. |
| **AltinAPI / Hasfiyat / CollectAPI (ücretli plan)** | Plan dahilinde | Ticari kullanım için doğru yol — ama sözleşmede **display/redistribution** maddesini kontrol et: "veriyi içeride sinyal hesabında kullanmak" ile "fiyatı son kullanıcıya göstermek" çoğu sağlayıcıda **ayrı haklardır**, gösterim için ayrı tarife olabilir. |
| **Ons için lisanslı feed** | — | Metals-API / TwelveData / Polygon ücretli planları ticari kullanım içerir. CME (GC futures) verisi ayrıca borsa ücreti (exchange fee) gerektirir — spot OTC feed tercih et. |
| **Harem Altın scraping** | Riskli | ToS ihlali + hukuki risk → yapma; aynı veriyi lisanslı satan AltinAPI'yi kullan. |

Genel kural: MVP'yi ücretsiz kaynaklarla yap, **para almaya başlamadan önce** her veri bacağı için
yazılı kullanım hakkını dosyala. Veri sağlayıcı sözleşmelerinde ayrıca uptime/SLA ve fiyat artış
maddelerine bak — ürünün tek kritik bağımlılığı bu olacak.

---

## 2. Makro Bağlam ve Ayrıştırma

### 2.1 Hareket ayrıştırma (dekompozisyon)

Gram TL üç bileşenin çarpımıdır; log-getiri ile toplamsal ayrışır:

```
Δln(gram TL) = Δln(XAU/USD) + Δln(USD/TRY) + Δln(1 + prim)
```

Örnek çıktı formatı ("son 1 ayda gram %X arttı" sorusunun cevabı):

| Bileşen | Katkı |
|---|---|
| Ons (XAU/USD) | +3.1% |
| Kur (USD/TRY) | +1.8% |
| Kapalıçarşı primi | +0.4% |
| **Toplam gram TL** | **+5.4%** |

Bu tablo ürünün her günlük raporunda olmalı — kullanıcının "altın mı yükseldi, TL mi düştü?"
sorusunun tek dürüst cevabı budur.

### 2.2 İzlenecek seriler ve kaynakları

**Küresel taraf:**
- **ABD 10Y reel faiz (TIPS, FRED: `DFII10`)** — onsun en güçlü ters korelasyonu. Reel faiz ↓ → ons ↑.
- **DXY** — ikincil ters korelasyon.
- **Fed beklentileri** — CME FedWatch; haber/etkinlik takvimi olarak besle.
- **Merkez bankası alımları** — World Gold Council çeyreklik raporları (TCMB son yıllarda en büyük alıcılardan; bu yapısal bir taban talep).
- **SPDR GLD tonajı** — spdrgoldshares.com günlük CSV; ETF giriş/çıkışı Batı yatırımcı iştahının göstergesi.
- **Jeopolitik risk** — olay bazlı; haber akışından etiketle, sayısallaştırmaya çalışma.

**Türkiye tarafı:**
- **TCMB politika faizi + Piyasa Katılımcıları Anketi** (EVDS) — beklenen enflasyon ve faiz patikası.
- **TÜFE + İTO geçim endeksi** — "altın enflasyona karşı korudu mu?" cevabı: gram getiri − TÜFE.
- **Mevduat faizi** (EVDS, ağırlıklı ortalama) — altın tutmanın fırsat maliyeti. Stopaj sonrası net faiz kullan.
- **KKM bakiyesi** (BDDK haftalık) — çözülme dövize/altına talep yaratır.
- **CDS 5Y** — ücretsiz güvenilir API yok; yaklaşık takip için haber/manuel ya da ücretli kaynak.
- **Darphane basım / ithalat verileri** — TÜİK dış ticaret (altın ithalatı) aylık; fiziki talebin resmi izi.

### 2.3 Rejim tanımı

Sinyalleri tekil değil, rejim kombinasyonu olarak değerlendir. Örnek rejim matrisi:

| Rejim | Ons 200GMA | ABD reel faiz trendi | Kur rejimi | Tarihsel gram davranışı |
|---|---|---|---|---|
| A | Üstünde | Düşüyor | Baskılanıyor | Gram yatay/birikim, prim düşük → **birikim penceresi** (kur düzeltmesi geldiğinde gram sıçrar) |
| B | Üstünde | Düşüyor | Serbest/zayıflıyor | En güçlü gram rejimi |
| C | Altında | Yükseliyor | Baskılanıyor | Gram için en zayıf rejim; mevduat fırsat maliyeti yüksek |
| **D** | Değişken | Yükseliyor | — | **Merkez bankası alım rejimi** — klasik korelasyon bozulur (aşağıda) |

2021-2025 dönemi B ve A arasında gidip geldi; "kur baskılanırken prim düşer, seçim/serbestleşme
sonrası tek seferde telafi gelir" örüntüsü (2023 seçim sonrası gibi) rejim analizinin ana bulgusudur.

> **Dipnot — Rejim D (merkez bankası alım rejimi):** Kadran panelindeki "reel faiz ↑ / DXY ↑ →
> ons ↓" mantığı, merkez bankalarının (TCMB, PBoC, RCB dahil) rekor fiziki altın aldığı dönemlerde
> **bozulur**. 2022-2024'te ABD reel faizleri yükselirken ve dolar güçlüyken ons tarihsel
> korelasyonun tersine yükseldi — çünkü fiyatı belirleyen Batı ETF akışı değil, resmi sektör taban
> talebiydi. Pratik sonuç: panel "olumsuz" derken ons yükselmeye devam edebilir. Bu yüzden panel
> "kesin yön" değil "bağlam" olarak sunulur; WGC çeyreklik merkez bankası alım verisi bir üst-filtre
> (rejim anahtarı) olarak izlenmeli. Alım rejimi aktifken reel-faiz/DXY göstergelerinin ağırlığı düşürülür.

### 2.4 EVDS seri kodları

**Doğrulanmış kodlar** (dış kaynaklarla teyitli, doğrudan kullanılabilir):

| Seri | Kod | Frekans |
|---|---|---|
| USD/TRY alış (TCMB) | `TP.DK.USD.A.YTL` | Günlük |
| USD/TRY satış (TCMB) | `TP.DK.USD.S.YTL` | Günlük |
| EUR/TRY alış | `TP.DK.EUR.A.YTL` | Günlük |
| TÜFE endeksi (2003=100) | `TP.FE.OKTG01` | Aylık |

**Yüksek olasılıklı — ilk çalıştırmada keşif script'iyle teyit et:**

| Seri | Muhtemel kod/grup | Not |
|---|---|---|
| Külçe altın satış (İst. serbest piyasa, TL/gr) | `TP.MK.KUL.YTL` | "Altın Fiyatları" veri grubu — Kapalıçarşı'nın **resmî tarihsel proxy'si**, backtest için kritik |
| Cumhuriyet altını satış | `TP.MK.CUM.YTL` | Aynı grup |
| Mevduat faizi, ağırlıklı ort. (açılan, TL, vadeye göre) | `TP.TRY.MT02`…`MT06` (1 ay → 1 yıl+) | Haftalık |
| TCMB ağırlıklı ort. fonlama maliyeti | `TP.APIFON4` | Günlük |
| Politika faizi (1 hafta repo) | "TCMB Faiz Oranları" grubundan keşfet | |
| 12 ay sonrası TÜFE beklentisi | "Piyasa Katılımcıları Anketi" grubundan keşfet | Aylık |
| KKM bakiyesi | "Kur Korumalı Mevduat" grubundan keşfet (alternatif: BDDK haftalık bülten) | Haftalık |

**Keşif script'i** — EVDS'nin kendi endpoint'leri kodların otoritatif kaynağıdır (API key header'da):

```python
import requests

KEY = "EVDS_API_KEYINIZ"
BASE = "https://evds2.tcmb.gov.tr/service/evds"
H = {"key": KEY}

# 1) Ana kategoriler
cats = requests.get(f"{BASE}/categories/type=json", headers=H).json()
# 2) Bir kategorinin veri grupları (ör. mode=2 + CATEGORY_ID)
groups = requests.get(f"{BASE}/datagroups/mode=2&code=<CATEGORY_ID>&type=json", headers=H).json()
# 3) Bir veri grubunun serileri → SERIE_CODE listesi
series = requests.get(f"{BASE}/serieList/type=json&code=<DATAGROUP_CODE>", headers=H).json()
# 4) Veri çekme
data = requests.get(
    f"{BASE}/series=TP.DK.USD.S.YTL&startDate=01-01-2015&endDate=07-07-2026&type=json",
    headers=H,
).json()
```

Bu script'i kurulumun parçası yap: ilk çalıştırmada "Altın Fiyatları", "Faiz İstatistikleri",
"Beklenti Anketleri" gruplarını dolaşıp bulduğu kodları `evds_series.json` config'ine yazsın —
kod değişirse (TCMB ara sıra seri yapısını değiştiriyor) tek dosya güncellenir.

---

## 3. Strateji Üretim Katmanı (asıl katma değer)

"Yükselir mi?" değil, **koşullu ve karşılaştırmalı** sorular. Motorun üreteceği dört analiz tipi:

### 3.1 Karşılaştırmalı beklenen getiri matrisi

Girdi: mevduat faizi (net), beklenen enflasyon (anket), mevcut prim, ons/kur senaryoları.
Çıktı: 6 ay vadede TL mevduat / gram / USD / (istenirse BIST) için iyimser-baz-kötümser reel getiri tablosu.

```
Gram senaryo getirisi = (1 + ons senaryosu) × (1 + kur senaryosu) × (1 + prim normalleşmesi) − 1
Reel getiri           = (1 + nominal) / (1 + gerçekleşen TÜFE) − 1
```

Mevduatın getirisi kesin, altınınki dağılımdır — çıktıda bunu açıkça söyle (mevduat: tek sayı,
altın: aralık). Bu dürüstlük ürünün güvenilirlik farkı olur.

### 3.2 Prim ortalamaya dönüş sinyali

- Prim serisinin (Kapalıçarşı has vs teorik) genişleyen-pencere z-skorunu tut.
- Tarihsel olarak prim aşırılıkları ortalamaya döner: prim > +2σ → "pahalı, alım için acele etme";
  prim < −1σ → "teorik değerin altında, birikimci için uygun pencere".
- Aynısını çeyrek/gram makası için: "çeyrek primi şu an %X, tarihsel dağılımda p85 → fiziki alacaksan
  gram/külçe al, çeyrek alma; düğün sezonu sonrası prim normalleşince çevir."

### 3.3 DCA (düzenli birikim) optimizasyonu

Backtest edilecek hipotezler: ay içi gün etkisi (genelde zayıf/istatistiksel olarak anlamsız — bunu
dürüstçe raporla), prim-koşullu alım (prim < medyan iken al — genelde anlamlı fark yaratır),
ATR-düşüş koşullu alım (haftalık düşüş > 1 ATR ise o haftanın payını öne çek).
Çıktı: "koşulsuz DCA vs koşullu DCA son 5 yıl fark: +X puan, maksimum geri çekilme: Y".

### 3.4 Kademe ve zarar-kes (ATR bazlı)

```
ATR(14) günlük gram TL üzerinden.
Kademeli alım: 3 kademe → şimdiki fiyat, −1.5 ATR, −3 ATR.
Zarar-kes (trend stratejisi için): giriş − 2.5~3 ATR ya da 200GMA altına günlük kapanış.
```
Not: birikimci profil için zarar-kes ANLAMSIZDIR (TL bazında nominal düşüş uzun vadede telafi
edilegelmiş) — profil ayrımı burada kritik.

### 3.5 Kullanıcı profilleri → farklı çıktı

| Profil | Ufuk | Ana sinyaller | Çıktı dili |
|---|---|---|---|
| Birikimci (enflasyon korunması) | 1 yıl+ | Prim z-skoru, çeyrek/gram seçimi, enstrüman maliyeti | "Bu hafta alım penceresi uygun/değil + hangi enstrüman" |
| Trend takipçisi | 1-6 ay | 50/200 GMA, rejim matrisi, ATR kademeleri | "Rejim B'de, pozisyon koru; geçersizlik: ons < X" |
| Makasçı/arbitraj | Gün-hafta | Prim aşırılıkları, sertifika/spot farkı, çeyrek primi | "Makas p95'te, normalleşme beklentisi" |

---

## 4. Teknik / Nicel Analiz

### 4.1 İki eksen ayrımı — kritik nokta

Ons ($) ve gram (TL) grafikleri **farklı yerlerde kırılır** ve farklı davranır:
- **Ons:** klasik teknik analiz çalışır (küresel, likit, çift yönlü piyasa). 50/200 GMA, RSI, MACD,
  Bollinger, destek/direnç anlamlıdır.
- **Gram TL:** kalıcı enflasyonist trend nedeniyle osilatörler yanıltır — RSI aylarca aşırı alımda
  kalır, "aşırı alım = sat" sinyali TL'de sistematik zarar ettirir. Gram tarafında trend göstergeleri
  (GMA'lar, ATR) ve **prim/makas** kullan; osilatörleri sadece ons tarafında çalıştır.
- Gram TL'de "destek" çoğu zaman teknik değil politiktir (kur rejimi tabanı).

### 4.2 Backtest metodolojisi ("kesin strateji" iddiasını taşıyabilecek tek şey)

- Format: "Sinyal S son 5 yılda N kez oluştu → sonraki 1/3/6 ay getiri dağılımı: medyan, p25-p75,
  kazanma oranı, en kötü durum." N < 15 ise **raporlama ama 'istatistiksel olarak zayıf' etiketi koy**.
- Tuzaklar: look-ahead bias (sinyal günü kapanışıyla işlem varsayma, ertesi gün açılış kullan),
  2018/2021/2023 kur şoklarının tek başına tüm getiriyi sürüklemesi (medyan + ortalama birlikte ver),
  Kapalıçarşı tarihsel verisinin yokluğu (kendi arşivin dolana kadar prim backtestleri kısa kalacak).
- Out-of-sample ayır: parametreyi 2015-2022'de fit et, 2023+ ile test et.

### 4.3 Mevsimsellik takvimi

| Dönem | Etki |
|---|---|
| Mayıs-Eylül (TR düğün sezonu) | Çeyrek/ziynet primi genişler |
| Ramazan/Kurban bayramı öncesi | Kısa fiziki talep sıçraması |
| Eylül-Kasım (Hindistan Diwali + düğün) | Ons fiziki talep desteği |
| Ocak-Şubat (Çin yeni yılı) | Ons talep desteği |
| Aralık (yıl sonu) | Portföy dengeleme, TL'de bütçe/zam takvimi etkisi |

Mevsimselliği tek başına sinyal yapma; prim sinyalinin **beklenen** genişlemesini ayarlamak için kullan
(düğün sezonunda %X prim normaldir, aynı prim ocak ayında anomalidir).

---

## 5. Türkiye'ye Özgü Pratik Katman

### 5.1 Vergi (2026 ortası itibarıyla — üretim öncesi mali müşavirle doğrula)

| Enstrüman | Vergi durumu |
|---|---|
| **Fiziki altın (ziynet/külçe)** | Bireysel alım-satımda gelir vergisi yok (ticari boyuta ulaşmadıkça). Külçe/ziynet KDV istisnalı; **işçilik kısmı KDV'ye tabi**. |
| **Banka altın hesabı (kaydi)** | Fiziki teslimatsız alımda **binde 2 kambiyo vergisi (BSMV)**. Bireyde değer artışı gelir vergisine tabi değil. |
| **Altın yatırım fonları** | Fon getirisi stopajı **%15** (26 Mart 2026'da %7.5'ten yükseltildi — bu tarz oranlar sık değişiyor, dinamik parametre yap). |
| **ALTINS1 (Darphane sertifikası)** | BIST'te menkul kıymet; kendi stopaj rejimi. Alım-satım komisyonu binde mertebesinde. |
| **BES altın fonları** | Devlet katkısı + uzun vadede stopaj avantajı; erken çıkış cezaları ayrı hesap ister. |

**Ürün çıkarımı:** strateji karşılaştırmalarında her zaman **vergi ve makas sonrası net getiri** göster.
%15 stopajlı fon ile binde 2 + %1 makaslı banka hesabı arasındaki sıralama, vade uzadıkça değişir —
bu hesaplayıcı tek başına bir özellik.

### 5.2 Enstrüman seçim matrisi ("altını neyle tutmalıyım?")

| Enstrüman | Alış-satış maliyeti (yaklaşık) | Saklama/risk | Uygun profil |
|---|---|---|---|
| Kuyumcu gram/külçe | %1.5-4 makas + sahtecilik riski | Fiziki saklama | Yastık altı isteyen, çok uzun vade |
| Çeyrek/ziynet | Makas + sezonluk prim (geri satışta erir) | Fiziki | Hediye/düğün; yatırım için genelde grama kaybeder |
| 22 ayar bilezik | İşçilik geri satışta **tamamen yanar** | Fiziki | Yatırım aracı DEĞİL — kullanıcıya bunu açıkça söyle |
| Banka altın hesabı | %1-2 makas + binde 2 BSMV | Yok (kaydi) | Aktif al-sat, orta vade |
| ALTINS1 / BYF | Binde birkaç komisyon, dar makas | Yok | Maliyet duyarlı, BIST hesabı olan |
| Altın fonu / BES | Yönetim ücreti + %15 stopaj | Yok | Uzun vadeli, işlemsiz birikimci |

### 5.3 Milyem/işçilik hesabı (kullanıcıların en çok soracağı)

```
Bilezik değeri (hurda) = brüt gram × 0.916 × has gram fiyatı
Ödenen fiyat           = hurda değeri + işçilik (%X)
→ Geri satışta işçilik + makas kaybedilir; başabaş için gramın en az o kadar yükselmesi gerekir.
```
Ürüne "bilezik başabaş hesaplayıcı" koy — Türkiye pazarında az bulunan, çok aranan bir özellik.

---

## 6. Ürünleşme Kararları

### 6.1 Veri çekme sıklığı

| Katman | Sıklık |
|---|---|
| Canlı fiyat gösterimi | WebSocket ya da 30-60 sn poll |
| Sinyal motoru (prim, makas, ATR) | 5 dk |
| Makro seriler (faiz, TÜFE, GLD, KKM) | Günlük (yayın saatinde) |
| Backtest/rejim yeniden hesabı | Günlük gün sonu |

### 6.2 Bildirim eşikleri

| Tetik | Eşik | Not |
|---|---|---|
| Teorik fiyat sapması (prim) | \|prim\| > %1.5 **veya** z > 2 | Mutlak + istatistiksel çift eşik; sadece mutlak eşik enflasyonla anlamını yitirir |
| Makas genişlemesi | > tarihsel p90 | Panik göstergesi |
| Günlük hareket | > 2 × ATR(14) | Hem gram TL hem ons için ayrı |
| Çeyrek primi | z > 2 (sezon düzeltmeli) | "Fiziki alma/çevir" bildirimi |
| Ons teknik | 50/200 GMA kesişimi, kritik seviye kırılımı | Günde en fazla 1 |
| Kur şoku | Günlük kur hareketi > 2 ATR | Gram bildirimiyle birleştir, ayrı gönderme |

Bildirim yorgunluğuna karşı: kullanıcı başına günlük maksimum bildirim sayısı + aynı sinyalin
tekrarına en az 24 saat soğuma.

### 6.3 Strateji çıktı formatı (her sinyal için zorunlu üçlü)

```json
{
  "sinyal": "birikim_penceresi",
  "yon": "alim_lehine",
  "profil": ["birikimci"],
  "gerekce": [
    "Kapalıçarşı primi %-0.8 (z=-1.6, son 2 yılın p8'i)",
    "Ons 200GMA üzerinde, ABD 10Y reel faiz 3 aydır düşüşte",
    "Çeyrek primi p40 — fiziki alım için çeyrek/gram farkı nötr"
  ],
  "guven": "orta",
  "gecersizlik": "Ons 200GMA altına günlük kapanış yapar VEYA prim +%1 üzerine çıkarsa bu değerlendirme geçersizdir",
  "ufuk": "1-3 ay",
  "uyari": "Bu içerik genel bilgilendirme amaçlıdır, yatırım tavsiyesi değildir."
}
```

Gerekçe + güven düzeyi + geçersizlik koşulu üçlüsü hem SPK açısından savunulabilir hem de
kullanıcı güveni açısından "kesin strateji" iddiasından daha ikna edicidir.

### 6.4 AI prompt tasarımı

- Modele ASLA "güncel fiyat nedir" sorma. Her çağrıda yapılandırılmış veri paketi ver:

```json
{
  "tarih": "2026-07-07T14:30+03:00",
  "ons_usd": 0.0, "usdtry": 0.0,
  "gram_teorik": 0.0, "gram_kapalicarsi_alis": 0.0, "gram_kapalicarsi_satis": 0.0,
  "prim_pct": 0.0, "prim_z": 0.0,
  "makas_pct": 0.0, "makas_percentile": 0,
  "ceyrek_prim_pct": 0.0, "ceyrek_prim_z_sezonsuz": 0.0,
  "atr14_gram": 0.0, "gunluk_degisim_atr": 0.0,
  "ons_200gma_ustu": true, "reel_faiz_us10y": 0.0, "reel_faiz_trend": "dusus",
  "tcmb_faiz": 0.0, "mevduat_net": 0.0, "beklenen_tufe_12ay": 0.0,
  "rejim": "A", "mevsim": "dugun_sezonu"
}
```

- System prompt'a sabitle: rol (genel yatırım bilgilendirmesi, kişiye özel tavsiye YASAK),
  çıktı şeması (6.3'teki JSON), dil kuralları ("kesinlikle", "garanti" yasak; "tarihsel olarak",
  "senaryo" zorunlu), geçersizlik koşulu üretme zorunluluğu.
- Deterministik hesapları (prim, z-skor, ATR, dekompozisyon) **kodda yap**, modele hazır ver;
  modeli sadece sentez/anlatı/senaryo için kullan. Model aritmetiği güvenilmezdir.

---

## 7. Hukuki Çerçeve (SPK)

- Dayanak: 6362 sayılı SPKn + **III-37.1 Tebliği**. **Yatırım danışmanlığı** = belirli kişiye,
  onun mali durumuna özel yönlendirme → lisanslı yatırım kuruluşu tekelinde. **Genel yatırım
  tavsiyesi** de tebliğde düzenlenmiş bir yan hizmettir; güvenli alan **"genel bilgilendirme /
  finansal veri sunumu"**dur.
- Pratik kurallar:
  1. Kişiye özel yönlendirme yok: "SEN şimdi al" değil, "prim tarihsel ortalamasının altında" formu.
  2. Kullanıcının portföyüne/mali durumuna göre kişiselleştirilmiş al-sat önerisi üretme (profil
     ayrımı "hangi metrikleri gösterelim" düzeyinde kalmalı, "sana özel emir" düzeyine geçmemeli).
  3. Her çıktıda feragatname; onboarding'de açık kabul.
  4. "Kesin strateji", "garantili getiri" ifadeleri hem yanıltıcı ticari uygulama (tüketici mevzuatı)
     hem SPK riski — ürün dilinden tamamen çıkar. Yerine: "senaryo analizi", "tarihsel istatistik",
     "sinyal + geçersizlik koşulu".
  5. Fiziki altın SPK enstrümanı değildir ama ALTINS1/fon/BYF hakkında konuştuğun anda sermaye
     piyasası aracı alanındasın — dikkat düzeyini ona göre kur.
- Örnek feragatname:
  > "Bu uygulamadaki içerikler genel bilgilendirme amaçlıdır; SPK mevzuatı kapsamında yatırım
  > danışmanlığı değildir. Yatırım danışmanlığı hizmeti, yetkili kuruluşlarca kişilerin risk ve
  > getiri tercihleri dikkate alınarak imzalanacak sözleşme çerçevesinde sunulur. Burada yer alan
  > değerlendirmeler mali durumunuza uygun olmayabilir; kararlarınızın sorumluluğu size aittir."
- Yayına almadan önce bir sermaye piyasası avukatından görüş al — bu doküman hukuki danışmanlık değildir.

---

## Önerilen Yol Haritası

1. **MVP (1-2 hafta):** Truncgil/AltinAPI + yfinance + EVDS → prim, makas, çeyrek primi, dekompozisyon hesabı → günlük özet raporu + veri arşivleme (SQLite) + **piyasa durum makinesi (1.3)** — hafta sonu sahte sinyal üretmemek MVP'nin parçası, sonraya bırakılamaz.
2. **v2:** ATR/GMA sinyalleri, bildirim motoru (eşik tablosu), enstrüman net-getiri hesaplayıcı, bilezik/milyem hesaplayıcı.
3. **v3:** Backtest altyapısı (sinyal → forward-return dağılımı), rejim matrisi, AI sentez katmanı (6.4'teki paket + 6.3'teki şema).
4. **Sürekli:** kendi Kapalıçarşı tick arşivini büyüt — uzun vadede projenin savunulabilir tek varlığı bu.

### Backlog (MVP Faz 1 tamamlandı — sıradakiler)

**MVP Faz 1 (bitti):** veri toplayıcı, durum makinesi, prim/makas/dekompozisyon/dolar-bazlı getiri,
EVDS makro bağlam + 5 yıl backfill, gösterge uzlaşı paneli, günlük rapor + Telegram botu, dönen loglar,
Oracle systemd dağıtımı. Hedef ortam Oracle Always Free.

**v2 — Bildirim & sinyal motoru:**
- Eşik bazlı bildirim (prim |>%1.5| veya z>2, makas > p90, günlük hareket > 2 ATR, çeyrek primi z>2).
- Bildirim yorgunluğu kontrolü (günlük tavan + 24s soğuma).
- Sinyal çıktısı üçlü format (gerekçe + güven + geçersizlik koşulu).
- Enstrüman net-getiri hesaplayıcı + bilezik/milyem başabaş hesaplayıcı.
- Rejim D anahtarı: WGC merkez bankası alım verisiyle panel ağırlıklandırma.

**v3 — Backtest & zeka:**
- Backtest altyapısı (sinyal → 1/3/6 ay forward-return dağılımı; kendi prim arşivi doldukça).
- AI sentez katmanı (6.4 veri paketi → 6.3 JSON şeması).
- **Google Trends "gram altın" kalabalık göstergesi** — perakende ilgi zirvesi çoğu zaman
  yerel tepe ile çakışır; ters-gösterge (contrarian) adayı olarak panele eklenir.
