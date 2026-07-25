# TESLIMAT ARŞİVİ — İnşa Dönemi (Faz 1-7)

**Dönem:** 2026-07-07 → 2026-07-21 · **Sonuç:** sistem GitHub Actions'ta otonom çalışıyor.

Bu dosya inşa döneminin **kanıt kaydıdır**: her fazda ne ölçüldü, hangi iddia doğrulandı,
hangisi **geri çekildi**, hangi hatanın kök sebebi neydi, neyin bilerek yapılmadığı.
Yedi ayrı `TESLIMAT*.md` dosyası burada birleştirildi; çalışmayan tekrar-üretim komutları
(Windows dönemi) ve o gün açık olup sonradan kapanan "bilinen eksikler" listeleri atıldı.

> Güncel kullanım için: [README.md](../README.md) · günlük izleme için [İZLEME.md](../İZLEME.md)
> · teknik derinlik için [PROJE-REHBERI.md](../PROJE-REHBERI.md) · mimari kararlar için
> [ai/DECISIONS.md](../ai/DECISIONS.md).

## Test ilerlemesi

| Faz | Tarih | Test | Ana teslim |
|---|---|---|---|
| 1 | 2026-07-07 | 31 | Telegram + EVDS canlı, rapor zenginleştirme |
| 2 | 2026-07-07 | 61 | Tarihsel veri katmanı, backtest, sinyal motoru, hesaplayıcılar |
| 3 | 2026-07-07 | 69 | Backtest metodoloji düzeltmesi, GitHub Actions, AI paket, Trends |
| 4 | 2026-07-07 | 79 | Tam otonomluk: Actions'ta bildirim + günlük rapor |
| 5 | 2026-07-07 | 91 | Sertleştirme, gizlilik, repo şişme önlemi (SQL dump) |
| 6 | 2026-07-21 | 135 | Onarım + grafik yorumlama katmanı (destek/direnç) |
| 7 | 2026-07-21 | 137 | Z-skor kapısı gün tabanına alındı, doküman sadeleştirme |

---

# Faz 1 — Canlıya alma (Telegram + EVDS)

**Kapsam kararı:** Windows 7/24 kalıcı çalıştırma **iptal** (kurulan artefaktlar temizlendi:
6 süreç durduruldu, zamanlanmış görevler ve startup VBS silindi). 7/24 çalıştırma sonraki
fazda GitHub Actions'a verildi.

### EVDS — endpoint ve ayrıştırma düzeltmesi
Eski `evds2/service/evds` SPA'ya yönleniyordu; doğru servis `https://evds3.tcmb.gov.tr/igmevdsms-dis`.
EVDS değerleri **nokta-ondalıklı** (`46.8204`), TR virgülü değil → ayrı parser (yoksa 10× hata).

### Seri teyit tablosu

| Amaç | Kod | Frekans |
|---|---|---|
| USD alış/satış | TP.DK.USD.A.YTL / .S.YTL | günlük |
| EUR alış | TP.DK.EUR.A.YTL | günlük |
| TÜFE endeksi | TP.FE.OKTG01 | aylık |
| **Külçe altın (Kapalıçarşı proxy)** | **TP.MK.KUL.YTL** | aylık |
| Cumhuriyet altını | TP.MK.CUM.YTL | aylık |
| Politika faizi (AOFM proxy) | TP.APIFON4 | günlük |
| Mevduat 1ay/3ay/6ay/1yıl | TP.TRY.MT02/03/04/06 | haftalık |
| 12 ay TÜFE beklentisi | TP.ENFBEK.PKA12ENF | aylık |

**Bulunamayan:** saf "1 hafta repo politika faizi" tek serisi (`TP.PY.P01`, `TP.APIFON1`,
`TP.MEVDUATTL` → 400). Çözüm: **TP.APIFON4 (AOFM)** — pratikte efektif politika faizi.

Backfill yıl-yıl chunk'landı (EVDS ~1000 satır/istek sınırı) → `evds_daily` 7531 satır,
2015-2026. Keşif: 597 altın + 2080 faiz + 1845 anket serisi → `evds_series.json`.

### Çözülen 2 gerçek hata
1. **Non-ASCII yol SSL hatası:** proje yolu `altın` içerdiği için `curl_cffi` cacert'i
   açamıyordu (yfinance çekimi kırıktı). `util._ensure_ascii_cert()` cacert'i ASCII temp
   yola kopyalar. *(Bu kod hâlâ duruyor — non-ASCII yol kullanan herkes için geçerli.)*
2. **yfinance `period=300d` geçersiz** → `1y` + fallback ticker.

### Telegram tuzak çözümleri
Raporlar **düz metin** (Markdown/HTML kaçış tuzağı yok); `/durum` **HTML** + `html.escape`;
4096 karakter sınırı için **satır sınırında** bölme.

---

# Faz 2 — Tarihsel katman, backtest, sinyaller

### KRİTİK: `evds_daily` tarih ISO düzeltmesi
**Kusur:** tarihler ham `GG-AA-YYYY` metniydi → `ORDER BY date` kronolojik değildi
(`"01-01-2018" < "01-02-2016"`). **Çözüm:** `evds.to_iso_date()` — günlük/aylık/çeyreklik
hepsi ISO'ya. 7531 satır silinip yeniden backfill edildi. Diğer tablolar denetlendi:
yalnız `evds_daily` bozuktu. Regresyon testi: `tests/test_evds_dates.py`.

### Tarihsel veri
`history_daily` **2549 gün** (2016-01-04 → 2026-07-07). `XAUUSD=X` 404 verdiği için
**GC=F futures** kullanıldı.

**Külçe saflık tespiti:** külçe/teorik oran medyanı **1.0105** → **has (1000/1000) bazı**
(995 değil; %1 fark GC=F contango'sundan).

**Veri kalitesi:** günlük vol %1.50; **3 aykırı (>6σ) hepsi gerçek kur şoku** — 2018-08-14
(+16%, lira krizi), 2021-12-22 (−25%, KKM günü), 2026-01-30 (−11%). Veri hatası değil.

### Backtest ilk sonuçları — **Faz 3'te ÇÖKTÜ, aşağıya bakınız**
Bu fazda rejim matrisi ve prim-koşullu DCA "doğrulanmış" ilan edilmişti. Faz 3'te metodoloji
düzeltilince bu hükümler geri çekildi. Sayılar tarihsel kayıt olarak duruyor ama
**hükümleri geçersizdir.**

### Sinyal motoru
Her sinyalde zorunlu dörtlü: **gerekçe + güven + geçersizlik + backtest köprüsü**.
Backtest karşılığı olmayan sinyaller açıkça "tarihsel doğrulaması yok" yazar.

### Hesaplayıcılar
`/net`, `/bilezik` — fon %15 stopajla en geride, ALTINS1 en düşük maliyetle önde.
Bilezik: %20 işçilik → başabaş için gram **+%20** (işçilik geri satışta yanar).

### GLD tonaj
Eski `spdrgoldshares.com` arşiv CSV'si artık **PDF** dönüyor. Çözüm: yfinance
`GLD.info totalAssets` → ton. Trend için arşiv birikmesi gerekiyordu.

---

# Faz 3 — Backtest metodolojisi düzeltildi (iddialar çöktü)

Bu faz, projenin ölçüm kültürünün kurulduğu yerdir.

### (1) Taban çizgisi + (2) örtüşmeyen pencere → rejim "üstünlükleri" ÇÖKTÜ

Faz 2 örtüşen pencere kullanıyordu ve taban çizgisi yoktu → **TL enflasyonu rejim başarısı
gibi görünüyordu.** Düzeltme: örtüşmeyen pencere (bağımsız örneklem) + "tüm günler" tabanına fark.

| Rejim | FAZ 2 (yanıltıcı) | FAZ 3 (düzeltilmiş) |
|---|---|---|
| A | "med +11.3%, kaz %88, DOĞRULANDI" | **fark −0.2p — üstünlük YOK** (~14 etkin dönem) |
| C | "med +8.1%" | fark −1.6p |
| D | "med +11.5%, kaz %91, DOĞRULANDI" | **fark +1.4p — marjinal, zayıf N** (~12) |
| B | "kaz %42" | fark −15.0p ⚠️ N=2 |
| Golden cross 6ay | "med +23.1%, kaz %97" | **fark +0.0p — üstünlük YOK** ⚠️ N=11 |

**Dolar bazlı (enflasyondan arınık): hiçbir rejimde anlamlı üstünlük yok.**

### (3) DCA adalet düzeltmesi
Prim-koşullu stratejide atlanan ay nakdi artık EVDS mevduatında net faizle işliyor (ölü nakit değil).

| Strateji | FAZ 2 | FAZ 3 (adil) | OOS (2023+) |
|---|---|---|---|
| DCA koşulsuz gram | +1736% (reel +43%) | +1736% (reel **+43%**) | reel −15% |
| DCA prim-koşullu | +2722% (şişik!) | +1697% (reel **+40%**) — koşulsuzdan **KÖTÜ** | reel −20% |
| TL mevduat | etiket belirsizdi | EVDS TP.TRY.MT06, net=brüt×0.85; reel −63% | reel −26% |

**❌ "Prim-koşullu üstünlük" çürütüldü** — Faz 2'deki fark ölü-nakit artefaktıydı.

### (4) Rehberdeki hükümler geri çekildi
`PROJE-REHBERI.md`'deki Faz 2 "DOĞRULANDI" blokları **geri çekildi.**

> _"Sayıların küçülmesi dürüstlüğün büyümesidir."_

### Google Trends — kontrarian DOĞRULANMADI
11 ilgi zirvesi sonrası gram TL 1ay **+6.4p**, 3ay **+8.3p taban ÜSTÜNDE** → momentum yönü,
kontrarian değil. **Ama N=4-6 (çok zayıf)** ve zirveler 2018/2021 kur krizleriyle çakışıyor
(enflasyon confounding). Sonuç: gösterge panelde kalır, **düşük güven / yön belirsiz**.

### GitHub Actions canlı
Repo: https://github.com/Mertsaglm/gold_tracking_system · 15 dk cron arşivleyici,
`GITHUB_TOKEN` ile commit/push, secret gerekmeden.

---

# Faz 4 — Tam otonomluk

**Tek cümle:** Kullanıcı hiçbir şey çalıştırmadan sistem kendi kendine izliyor, uyarıyor
ve raporluyor. **Üretim ortamı budur.**

### Secrets
`gh` kurulu değildi → GitHub API + PyNaCl sealed box (`scripts/set_secrets.py`).
3 secret eklendi; **hiçbir secret log/commit/koda girmedi.** Workflow izni en dar
(`contents: write`).

### Bildirim motoru (`src/notify.py`)
- Eşikler: `|prim| > %1.5` veya `z > 2` · makas > tarihsel p90 · günlük hareket > 2×ATR ·
  çeyrek primi `z > 2`
- **Yorgunluk kontrolü:** 24s soğuma + günlük tavan (6). Durum `data/alert_state.json`
- Üç bacak FRESH değilse anomali **bastırılır**; hafta sonu "pazartesi beklentisi" günde 1
- Her bildirimde zorunlu üçlü: kural + gerekçe/değer + geçersizlik + feragat

### Dakika bütçesi (ölçüldü)
Repo **public → sınırsız.** Arşiv ~30 sn, günlük ~202 sn. Aylık ≈ 2970 dk.
Private'a çevrilirse 2000 dk sınırı → sıklığı 30 dk'ya çekmek gerekir (≈1530 dk).

### Gizlilik notu
Repo public → `data/` ve `reports/` herkese açık (yalnız fiyat verisi/analiz, hassas değil).

---

# Faz 5 — Sertleştirme, gizlilik, repo şişme önlemi

### Gizlilik temizliği
İzlenen `.md` dosyalarındaki bot adı ve chat_id maskelendi (`<bot_adı>`, `<chat_id>`);
`git grep` ile **0 iz** doğrulandı. `logs/*.log` izlemeden çıkarıldı.
**Savunma katmanı:** `util.mask_pii()` + Telegram log'u chat_id'nin yalnız son 3 hanesini yazar.

**Git geçmişi kararı (gizlemeden):** eski commit'lerde chat_id hâlâ görünür. Chat ID düşük
riskli (bot'a mesaj atmak için token da gerekir; token secret'ta). Geçmiş yeniden yazma
(`filter-repo`) **zahmete değmez** — bilinçli karar.

### Bot komut yetkilendirmesi
`.env TELEGRAM_CHAT_ID` + config `extra_allowed_chat_ids` beyaz listesi. İzinsiz sohbet
**sessizce yoksayılır + loglanır.**

### Repo şişme önlemi (denetim bulgusu)
**Sorun:** günlük job SQLite binary'sini commit'liyordu → git her sürümü tam saklar.
Ölçüm: geçmişte 5 sürüm / 3252 KB, trajectory kötü (her gün +~800 KB).

**Çözüm:** `src/dbdump.py` **deterministik SQL text dump** (her tablo mantıksal anahtara göre
sıralı → günlük diff yalnız yeni satırlar) + `src/restore_db.py`. Binary gitignore'a alındı.
**Kanıt:** 844 KB binary yerine **59 satırlık text diff**; round-trip 8 tabloda birebir eşit.

---

# Faz 6 — Onarım + grafik yorumlama katmanı

### Sahte arşiv alarmı (raporu her gün kirleten hata)
**Belirti:** her raporda `⚠️ ~13 ardışık çalışma başarısız`, kapsama `%1`.
**Gerçek:** son 60 Actions çalışmasının **60'ı başarılı**.

**Kök sebep:** metrikler 7/24 collector senaryosuna göre hesaplanıyordu (dakikada bir tick),
sistem ise Actions'ta çalışıyor.

**Ölçüm — GitHub gerçekte ne teslim ediyor:** cron `*/15` (96/gün) yazıyor, gerçek
**10-17/gün** (13 Tem 10 · 14 Tem 15 · 15 Tem 14 · 16 Tem 14 · 17 Tem 15 · 18 Tem 17 ·
19 Tem 16 · 20 Tem 11). Aralar 1-3.5 saat. GitHub düşük aktiviteli repolarda zamanlanmış
iş akışlarını kısıtlıyor.

**Düzeltme:** `runtime_mode: actions|collector` + `effective_freq_minutes()`;
`archive_observed_freq_minutes: 90`; boşluk ancak toleransı (90×3=270 dk) aşarsa arıza sayılır.

### FRED zaman aşımı
`FRED DFII10 hata: Read timed out (25s)` — engelleme değil, **timeout**. Panel 5 yerine 3
göstergeyle çalışıyordu. Ayrıca aynı seri çağrı başına **3 kez** çekiliyordu.
Düzeltme: timeout 25→60 sn, 2 yeniden deneme, süreç içi memo (2. çağrı 0.60 sn → 0.0000 sn).

### Neden gram TL için OHLC ÜRETİLMEDİ
`high_gram ≠ high_ons × high_usdtry` — günün en yüksek onsu ile en yüksek kuru aynı ana
denk gelmez; çarpımları **gerçekte hiç işlem görmemiş** bir aralık üretir (şişmiş ATR +
hayali fitiller). Ayrıca TL serisi enflasyonla yapısal olarak yukarı kayar: 2 yıl önceki
"direnç" bugün direnç değil.

**Çözüm:** teknik seviyeler **ons USD üzerinde**, TL yalnız **bugünkü kurla izdüşüm**
olarak ve kullanılan kur yazılarak gösterilir.

### Kalibrasyon bulgusu (dürüst)
2 yıllık ons aralığı **%138 genişlikte** ve yalnız 30 pivot var. Güçlü trendde yatay
seviyeler doğal olarak az tekrar eder — `min_dokunus: 3` ile **hiç seviye çıkmıyordu**.
Tolerans 1 ATR'ye, min_dokunus 2'ye çekildi. Zayıflık gizlenmiyor: dokunuş sayısı ve skor
raporda görünür.

### **Seviyelerin yön üstünlüğü YOK** (ölçüldü)
Doğrulama harness'i sunumdan **önce** inşa edildi; ölçüm raporun dilini belirledi (tersi değil).
Look-ahead korumalı (`Pivot.confirm_idx`), örtüşmeyen pencere, koşulsuz taban.

| Sinyal | Ufuk | N | Taban farkı | Hüküm |
|---|---|---|---|---|
| Desteğe yakın | 1 ay | 50 | **−0.1p** | **kenar yok** |
| Dirence yakın | 1 ay | 51 | **+0.6p** | **kenar yok** |
| Desteğe yakın | 3 ay | 24 | −1.6p | zayıf kanıt |
| Desteğe yakın | 6 ay | 14 | +3.2p | ölçüm yetersiz |
| RSI aşırı satım | 1 ay | 16 | +2.1p | ölçüm yetersiz |
| Bollinger alt | 1 ay | 40 | +0.6p | kenar yok |

`edge_verdict()` kuralı: **zayıf N, büyük farkı EZER.** En güçlü ifade "zayıf kanıt"tır.

Ayrıca fiyat tüm zamanların zirvesindeyse: **"ÜSTTE DİRENÇ YOKTUR — o bölgede hiç işlem
geçmemiştir"** (perakende TA'nın sessizce direnç uydurduğu yer burasıdır; testli).

### Yarım bar tuzağı
`daily.yml` 15:35 UTC'de koşuyor, CME altın ~21:00 UTC'de kapanıyor → her çalışma **yarım
bar** görüyor. `son_bar_kapanmamis_atla: true` ile atılıyor; rapor hangi barı analiz ettiğini
yazıyor (`son KAPANMIŞ bar`).

---

# Faz 7 — Z-skor kapısı gün tabanına alındı

`config.yaml`'daki eşik baştan beri **gün** cinsindendi (`zscore_min_samples: 60`) ve rapor
`N/60 gün` yazıyordu; ama kapıyı yoklayan kod **kayıt** sayıyordu.

**Neden gün doğru birim:** arşiv gün içinde ~10 örnek alır ve bunlar birbirinin tekrarıdır
(otokorelasyon). Kayıt saymak bağımsız gözlem sayısını olduğundan büyük gösterir.

| Birim | Değer |
|---|---|
| Geçerli kayıt | 134 |
| Bu kayıtların kapsadığı farklı gün | **13** |
| Eşik | 60 |

Sinyal 60 günlük dağılım yerine **13 günlük** bir ortalamadan sapma ölçüyordu.

**Yapılan:** `db.count_valid_prim_days()` (`COUNT(DISTINCT date(ts_utc))`, hafta sonu ve
`indicative` hariç). Kapıyı yoklayan 5 nokta buna geçirildi: `signals.py`, `notify.py`,
`report.py`, `aipaket.py`. Rapor artık ikisini birlikte yazar
(`Prim kaydı: 200 (geçerli: 134 · 13 gün)`).

---

# Bilinçli olarak YAPILMAYANLAR

Bunlar unutulmuş değil, gerekçesiyle dışarıda bırakıldı — tekrar tartışmaya açmadan önce
gerekçeyi çürütmek gerekir.

| Yapılmayan | Gerekçe |
|---|---|
| **Hacim ağırlıklandırması** | GC=F hacmi ön-vade kontrat hacmi ve vade geçişinde süreksiz (2016'da 143, bugün 44.361 — likidite göçü); TRY=X hacmi 0. Gürültüyü titizlik kılığına sokardı. |
| **MACD** | Aynı kapanışın iki EMA'sı; panelde zaten olan 50/200 GMA ile eşdoğrusal. Uzlaşı paydasını kopya oyla şişirirdi. |
| **Fibonacci** | Salınım seçimi serbestlik derecesidir; dondurulmadan doğrulanamaz. |
| **gram TL OHLC** | Çarpım hiç işlem görmemiş aralık üretir (yukarıda). |
| **Git geçmişi yeniden yazma** | Eski commit'lerdeki chat_id düşük riskli; `filter-repo` zahmete değmez. |
| **Fiyat tahmini / yatırım tavsiyesi** | Kapsam dışı; her rapor feragatle biter. |

---

# Kalıcı dersler

1. **Örtüşen pencere + taban çizgisizlik = sahte üstünlük.** Faz 2'nin bütün "doğrulanmış"
   iddialarını Faz 3 bu iki düzeltmeyle çökertti.
2. **Zayıf N, büyük farkı ezer.** N=3 ile +5.0p fark "kanıt" değildir.
3. **Metrik yanlış kalibre edilirse sağlam sistem arızalı görünür** (Faz 6 sahte alarm).
4. **Türetilmiş fiyattan teknik seviye üretilmez** (gram TL OHLC).
5. **Sayıların küçülmesi dürüstlüğün büyümesidir.**

Sonraki dönemin kararları ve dersleri: [ai/DECISIONS.md](../ai/DECISIONS.md) ·
[ai/LESSONS.md](../ai/LESSONS.md).
