# TESLIMAT — Faz 6: Onarım + Grafik Yorumlama (destek/direnç + çoklu gösterge teyidi)

## Tek cümle
Yeniden klonlanan yerel kopya canlandırıldı, raporu her gün kirleten **sahte arıza alarmı**
düzeltildi, ve gerçek günlük OHLC üzerine kurulu bir **grafik yorumlama katmanı** eklendi —
seviyeler ölçüldü, **yön üstünlüğü çıkmadı ve bu saklanmadı.**

| Bölüm | Durum |
|---|---|
| A1. Yerel ortam (pull + restore) | ✅ history_daily 0 → 2549, evds_daily 0 → 7638 |
| A2. `XAUUSD=X` 404 düzeltmesi | ✅ commit'lendi (`ons_hist_primary: GC=F`) |
| A3. Sahte arşiv alarmı | ✅ kök sebep bulundu + kalibre edildi |
| A4. İZLEME.md gerçeğe uyduruldu | ✅ %80-95 → %60-100 + kısıtlama tablosu |
| A5. FRED Actions'ta boş dönüyordu | ✅ kök sebep timeout; 60 sn + retry + memo |
| B1. `ohlc_daily` veri katmanı | ✅ 2650 GC=F + 2745 TRY=X bar (2016→2026) |
| B2. Destek/direnç tespiti | ✅ fraktal pivot + ATR ölçekli kümeleme |
| B3. Çoklu gösterge teyidi | ✅ yapı/RSI/%B/ATR + sayılabilir teyit çetelesi |
| B4. Dürüst doğrulama harness'i | ✅ **kenar yok** (dürüst sonuç, aşağıda) |
| B5. Rapor + Telegram + `/grafik` | ✅ entegre, boru-tablosuz |
| **Testler** | ✅ **135/135** (91 → +44) |

---

## A3 — Sahte arşiv alarmı (raporu her gün kirleten hata)

**Belirti:** her raporda `⚠️ Arşiv uyarısı: ~13 ardışık çalışma başarısız`, kapsama `%1`.
**Gerçek:** son 60 Actions çalışmasının **60'ı başarılı**, günlük rapor her akşam düşüyor.

**Kök sebep:** metrikler 7/24 collector senaryosuna göre hesaplanıyordu (dakikada bir tick),
sistem ise Actions'ta çalışıyor. `archive_health` günde 96 çalışma bekliyordu
(`archive_freq_minutes: 15`), `coverage_report` günde 1440 kayıt (`poll_seconds: 60`).

**Ölçüm — GitHub gerçekte ne teslim ediyor:**

| Gün | Çalışma | | Gün | Çalışma |
|---|---|---|---|---|
| 13 Tem | 10 | | 17 Tem | 15 |
| 14 Tem | 15 | | 18 Tem | 17 |
| 15 Tem | 14 | | 19 Tem | 16 |
| 16 Tem | 14 | | 20 Tem | 11 |

Cron `*/15` (96/gün) yazıyor, gerçek **10-17/gün** — GitHub düşük aktiviteli repolarda
zamanlanmış iş akışlarını kısıtlıyor. Aralar 1-3.5 saat.

**Düzeltme:** `runtime_mode: actions|collector` + `effective_freq_minutes()`;
`archive_observed_freq_minutes: 90`; boşluk ancak toleransı (90×3=270 dk) aşarsa arıza sayılır;
kapsama uyarısı sayım yerine **boşluk tabanlı** (günlük çalışma sayısı 10-17 arası oynuyor).

**Kanıt:** düzeltme sonrası rapor — `kapsama %62 (10/16, actions ritmi)`, **uyarı satırı yok.**

## A5 — FRED

`20 Tem log'u: FRED DFII10 hata: Read timed out. (read timeout=25)` — engelleme değil,
**zaman aşımı**. Panel 5 yerine 3 göstergeyle çalışıyordu (payda daralıyor, sinyal zayıflıyor).
Ayrıca aynı seri **çağrı başına 3 kez** çekiliyordu (`build_panel` → report + signals + aipaket).

Düzeltme: timeout 25 → 60 sn, 2 yeniden deneme (geri çekilmeli), süreç içi memo.
Ölçüm: 2. çağrı 0.60 sn → 0.0000 sn.

---

## B1 — Veri katmanı

`history_daily` yalnız kapanış tutuyor ve `gram_teorik` **türetilmiş** bir fiyat; destek/direnç
ve hakiki ATR için yüksek/düşük şart. Yeni `ohlc_daily` tablosu:

| Sembol | Bar | Aralık |
|---|---|---|
| `GC=F` (ons) | 2650 | 2016-01-04 → 2026-07-21 |
| `TRY=X` (kur) | 2745 | 2016-01-01 → 2026-07-21 |

`dbdump._TABLES`'a eklendi → dump/restore gidiş-dönüşü doğrulandı (5395 satır hayatta kaldı,
testli). Dump 2.5 MB → 3.5 MB.

### gram TL için OHLC neden ÜRETİLMEDİ
`high_gram ≠ high_ons × high_usdtry` — günün en yüksek onsu ile en yüksek kuru aynı ana denk
gelmez; çarpımları **gerçekte hiç işlem görmemiş** bir aralık üretir (şişmiş ATR + hayali
fitiller). Ayrıca TL serisi enflasyonla yapısal olarak yukarı kayar: 2 yıl önceki "direnç"
bugün direnç değil, kurun çoktan geçtiği bir fiyattır (`backtest.py:440-441` aynı uyarı).

**Çözüm:** teknik seviyeler **ons USD üzerinde**, TL yalnız **bugünkü kurla izdüşüm** olarak
ve kullanılan kur yazılarak gösterilir:
`4,358–4,400 $ bandı · TL izdüşümü: kur 47.14 iken ~6,637 ₺/gram`

---

## B2/B3 — Seviye tespiti ve teyit

Fraktal swing pivot (k=10) → ATR ölçekli **yüzde** kümeleme (ölçekten bağımsız; seri
1.063'ten 5.586'ya gitti, mutlak tolerans yanlış olurdu) → medyan fiyat + `lo–hi` bandı.

**Kalibrasyon bulgusu (dürüst):** 2 yıllık ons aralığı **%138 genişlikte** (2.352→5.586) ve
yalnız 30 pivot var. Güçlü trendde yatay seviyeler doğal olarak az tekrar eder — tolerans
%1'de en büyük küme 2 dokunuş, `min_dokunus: 3` ile **hiç seviye çıkmıyordu**. Tolerans
1 ATR'ye, min_dokunus 2'ye çekildi (bir doğru için iki nokta). Zayıflık gizlenmiyor:
dokunuş sayısı ve skor (`sqrt(dokunuş)`) raporda görünür.

**Skor** = `sqrt(dokunuş) × 0.5^(yaş/180g) × karma primi(1.25)`. Yalnız gösterim sıralaması
içindir, olasılık olarak sunulmaz.

**Teyit çetelesi** — "birden fazla göstergeyle doğrulandı" ancak böyle denetlenebilir olur:
`✓2+ dokunuş ✓karma (kutup değişimi) ✓1y+2y pencerede ✓trend uyumlu ✗momentum uyumlu` → **4/5**

### Bilinçli dışarıda bırakılanlar
- **Hacim ağırlıklandırması YOK.** GC=F hacmi ön-vade kontrat hacmi ve vade geçişinde
  süreksiz (ölçüm: 2016'da 143, bugün 44.361 — likidite göçü, kanaat değil); TRY=X hacmi 0.
  Hacimle ağırlıklandırmak gürültüyü titizlik kılığına sokardı.
- **MACD YOK.** Aynı kapanışın iki EMA'sı; panelde zaten olan 50/200 GMA ile eşdoğrusal.
  Eklemek uzlaşı paydasını kopya oyla şişirir — Faz 3'te cezalandırılan hatanın aynısı.
- **Fibonacci YOK.** Salınım seçimi serbestlik derecesidir; dondurulmadan doğrulanamaz.

---

## B4 — Dürüst doğrulama: **seviyelerin yön üstünlüğü YOK**

Sunumdan **önce** inşa edildi ve çalıştırıldı; ölçüm sonucu raporun dilini belirledi (tersi
değil). Yürüyen-ileri seviye kurulumu, **look-ahead korumalı** (`Pivot.confirm_idx` — bir
pivot ancak k bar sonra bilinebilir), örtüşmeyen pencere, koşulsuz taban çizgisi.

| Sinyal | Ufuk | N | Taban farkı | Hüküm |
|---|---|---|---|---|
| Desteğe yakın | 1 ay | 50 | **−0.1p** | **kenar yok** |
| Dirence yakın | 1 ay | 51 | **+0.6p** | **kenar yok** |
| Desteğe yakın | 3 ay | 24 | −1.6p | zayıf kanıt (OOS'ta yetersiz) |
| Desteğe yakın | 6 ay | 14 | +3.2p | ölçüm yetersiz |
| RSI aşırı satım | 1 ay | 16 | +2.1p | ölçüm yetersiz |
| Bollinger alt | 1 ay | 40 | +0.6p | kenar yok |

**Sonuç:** 1 ay ufkunda (N=50-51, ~17 bağımsız dönem — iyi güç) **desteğe/dirence yakın olmak
sonraki ayın yönü hakkında bilgi taşımıyor.** 3-6 ay satırları hem N zayıf hem de birbiriyle
çelişiyor (destek 3ay −1.6p ama 6ay +3.2p) — 54 karşılaştırmada beklenen gürültü.

`edge_verdict()` kuralı: **zayıf N, büyük farkı EZER.** En güçlü ifade "zayıf kanıt"tır;
bundan ötesi bu N değerlerinde ruhsatlı değil.

**Rapor bu yüzden şunu yazar:**
> Seviyeler **geometridir, ölçüm değildir.** Fark ≈0 ise yön bilgisi yoktur — seviye yine
> kademe/stop planlaması için kullanılabilir (mekanik kural), **yön iddiası için kullanılamaz.**

Ayrıca fiyat tüm zamanların zirvesindeyse: **"ÜSTTE DİRENÇ YOKTUR — o bölgede hiç işlem
geçmemiştir"** (perakende TA'nın sessizce direnç uydurduğu yer burasıdır; testli).

---

## B5 — Entegrasyon

- `report.py` → `## Sinyaller` sonrası, `## Veri Kalitesi` öncesi; try/except + yerel import
  (bölüm kırılırsa rapor ölmez), veri yoksa **sessiz**.
- `build_weekly_report` `build_report`'u çağırdığı için pazar raporuna otomatik dahil.
- `daily_job` adım 3: artımlı OHLC (son 10 gün yeniden yazılır — yfinance yakın barları
  revize eder, tablo kendi kendini onarır).
- **Yarım bar tuzağı:** `daily.yml` 15:35 UTC'de koşuyor, CME altın ~21:00 UTC'de kapanıyor →
  her çalışma **yarım bar** görüyor. `son_bar_kapanmamis_atla: true` ile atılıyor; rapor
  hangi barı analiz ettiğini yazıyor (`son KAPANMIŞ bar`).
- Telegram: `parse_mode=None` boru tablolarını çorbaya çevirdiği için **madde işaretli**
  çıktı; `_md_to_plain()` sonrası okunabilirlik testli (`|` içermez).
- `/grafik` komutu (`refresh=False` — uzun yoklama döngüsü yfinance'te asılmasın).
- Ana panele **tek toplu oy** (`panele_katil`): 4 korelasyonlu fiyat türevi gösterge ayrı ayrı
  girseydi panel makro kılığında momentum göstergesine dönerdi (`ons_gma` zaten orada).
- `archive.yml` **değişmedi** — `notify.py` chart'ı import etmiyor (elle listelenen bağımlılık
  listesi bozulmadı). Yeni pip paketi yok (yfinance zaten `requirements.txt`'te).

---

## Test kırılımı (135)
Önceki 91 + `tests/test_chart.py` 44: pivot (4), kümeleme (3), seviye/skor (6), nearest (1),
extremes (1), ATR/TR (3), RSI (3), Bollinger (2), yapı (1), etiketleyiciler (6),
`edge_verdict` (4), teyit (2), format/Telegram güvenliği (5), DB gidiş-dönüş (2), diğer (1).

Konvansiyona uyuldu: saf fonksiyonlar test edilir, ağ çekicileri edilmez (mock yok),
eşikler literal argüman olarak geçer.

**En kritik assert** (`test_edge_verdict_weak_n_overrides_big_diff`): N=3 ile +5.0p fark
"ölçüm yetersiz" döner, "kanıt" kelimesi geçmez. Faz 3'te iddiaları çökerten şey tam olarak
az sayıda bağımsız gözlemdi.

## Bilinen eksikler / sonraki
- Seviyelerin yön üstünlüğü yok (ölçüldü). Kademe/stop planlaması için kullanılabilir.
- `/grafik` dahil interaktif bot komutları yerelde `src.telegram_bot` açıkken çalışır (Actions push-only).
- Yerel `.venv` Python 3.9.6, Actions 3.12 — şu an çalışıyor (29/32 dosyada
  `from __future__ import annotations`), ama sürüm kayması ileride kırabilir.
- `signals.evaluate_alerts` ile `notify.evaluate_thresholds` hâlâ ikiz eşik mantığı taşıyor.
- `build_report` artık 8 bölümlü tek akümülatör fonksiyon; bölüm kaydı (registry) refactor'ü
  iyileştirme olurdu ama kapsam dışı bırakıldı.

## Tekrar üretmek
```bash
git pull --rebase
.venv/bin/python -m src.restore_db
.venv/bin/python -m pytest -q                    # 135 test
.venv/bin/python -m src.ohlc_hist backfill       # 2650 + 2745 bar (tek sefer)
.venv/bin/python -m src.chart validate           # reports/grafik_dogrulama.md
.venv/bin/python -m src.chart                    # grafik bölümü (stdout)
.venv/bin/python -m src.report                   # tam rapor + Telegram
```
