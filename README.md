# Altın Takip

Türkiye altın piyasası veri toplayıcı + **piyasa durum makinesi** + günlük markdown/Telegram raporu.
Kişisel araç; ücretsiz kaynaklar.

**Üretim ortamı: GitHub Actions.** Sistem 7/24 kendi kendine çalışır — veri çeker, eşikleri
değerlendirir, Telegram'a rapor ve bildirim gönderir, arşivi repoya commit'ler. Kullanıcının
hiçbir şey çalıştırması gerekmez. Yerel kurulum yalnızca geliştirme ve on-demand analiz içindir.

> ⚠️ Genel bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.

## Ne yapar?

- **Kaynaklar:** Truncgil (serbest piyasa gram/çeyrek/tam/Cumhuriyet + USD), yfinance (ons XAU/USD +
  USD/TRY), TCMB EVDS (günlük; kur/faiz/TÜFE/altın/enflasyon beklentisi).
- **Arşiv:** ham tick + 1 dk OHLC → SQLite; EVDS tarihsel seriler `evds_daily`; günlük gerçek OHLC
  `ohlc_daily` (2016+).
- **Hesaplar:** teorik has gram, **prim** (saflık düzeltmeli), makas, çeyrek primi, **log-getiri
  dekompozisyonu** (ons/kur/prim), **dolar bazlı gram getirisi**, z-skor.
- **Durum makinesi:** her bacak `FRESH / STALE / CLOSED_WEEKEND / CLOSED_HOLIDAY`. Prim yalnız üç
  bacak FRESH iken **geçerli**; forex kapalıyken `indicative` (z-skor/backtest'ten dışlanır).
  Hafta sonu beklenti serisi + pazartesi mutabakatı.
- **Makro bağlam (EVDS):** politika faizi, net mevduat faizi, TÜFE, 12 ay enflasyon beklentisi,
  **reel net mevduat faizi**.
- **Gösterge uzlaşı paneli:** ABD 10Y reel faiz (FRED), DXY (FRED), ons 50/200 GMA (yfinance),
  TL reel net mevduat (EVDS), SPDR GLD tonaj, Google Trends — her biri olumlu/nötr/olumsuz +
  toplam uzlaşı skoru.
- **Grafik yorumu:** gerçek günlük OHLC üzerinde fraktal swing pivot → ATR ölçekli kümeleme ile
  **destek/direnç bantları**, dönemsel zirve/dip, RSI/Bollinger/trend yapısı ile **çapraz teyit
  çetelesi**. Seviyeler ons USD'de hesaplanır, TL'ye **bugünkü kurla izdüşüm** olarak çevrilir.
  Ölçüm sonucu: seviyelerin yön üstünlüğü yok — kademe/stop planlaması için sunulur, yön iddiası
  olarak değil (bkz. `TESLIMAT-FAZ6.md`).
- **Rapor:** gün sonu markdown → dosya + Telegram. Bot komutları: `/durum`, `/rapor`.
- **Loglama:** `logs/` altında dönen dosya logları (5 MB × 5).
- **Kapsama:** rapor "son 24s veri kapsaması %X, en uzun kesinti Y dk" satırı; z-skor yalnız FRESH
  kayıtları sayar.

## Proje yapısı

```
config.yaml          tüm eşik/URL/oran (kod içine sabit gömülmez)
holidays_tr.yaml     TR/US tatil takvimi (yılda bir güncelle)
.env                 EVDS + Telegram kimlikleri (git'e girmez)
evds_series.json     keşif çıktısı (teyitli + bulunan kodlar)
src/
  util.py            TR sayı ayrıştırma, zaman, config/env, SSL cacert ASCII fix
  calc.py            teorik gram, prim, makas, çeyrek primi, dekompozisyon, z-skor
  indicators.py      kadran/uzlaşı paneli (FRED/yfinance/GLD + etiketleme)
  market_calendar.py forex seansı + tatil + gündüz/gece
  state_machine.py   FRESH/STALE/CLOSED_* + prim geçerliliği
  db.py              SQLite şema + erişim
  sources/           truncgil.py, yf.py, evds.py
  collector.py       ana toplayıcı döngü
  ohlc_hist.py       günlük gerçek OHLC (yfinance → ohlc_daily); grafik katmanının verisi
  chart.py           destek/direnç + gösterge teyidi + doğrulama harness'i
  evds_job.py        EVDS backfill + günlük güncelleme + rapor bağlamı
  reconcile.py       pazartesi hafta sonu mutabakatı
  report.py          gün sonu markdown raporu
  telegram_bot.py    gönderim + /durum /rapor (long-polling)
  logging_setup.py   dönen dosya logları
  backup_db.py       güvenli SQLite dump (.backup API)
  evds_discover.py   EVDS kod keşfi
tests/               calc + durum makinesi + gösterge + grafik birim testleri (137 test)
```

## Yapılandırma

- `config.yaml`: tüm eşikler, URL'ler, seri kodları, oranlar. Kodda sabit yoktur.
- `.env` (`.env.example`'dan kopyala):
  - `EVDS_API_KEY` — https://evds2.tcmb.gov.tr → Profilim → API Key Kopyala
  - `TELEGRAM_BOT_TOKEN` — BotFather
  - `TELEGRAM_CHAT_ID` — @userinfobot

---

## Otonom sistem (üretim)

İki GitHub Actions workflow'u her şeyi yürütür; **Telegram'a kendiliğinden mesaj düşer.**

| Workflow | Sıklık | Ne yapar |
|---|---|---|
| `archive.yml` | 15 dk cron | Fiyat çeker → CSV → **bildirim eşiklerini değerlendirir** → tetikte Telegram → commit |
| `daily.yml` | Her gün 15:35 UTC (18:35 TR) | import → EVDS → OHLC → rapor → Telegram → commit (pazartesi mutabakat, pazar haftalık) |

**Secrets (repo Settings → Secrets → Actions):** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`EVDS_API_KEY`.

**Bildirim kuralları (rehber 6.2):** |prim| > %1.5 veya z > 2 · makas > tarihsel p90 ·
günlük hareket > 2×ATR · çeyrek primi z > 2. **Yorgunluk kontrolü:** aynı sinyale 24s soğuma +
günlük tavan (6). Üç bacak FRESH değilse (hafta sonu/tatil) anomali bastırılır; ayrı "pazartesi
beklentisi" mesajı günde 1. Durum `data/alert_state.json`'da.

**Veri kalıcılığı:** SQLite binary repoya girmez; `data/altin.sql` metin dump'ı commit'lenir
(`src/dbdump.py` / `src/restore_db.py`). Böylece repo şişmez ve geçmiş diff'lenebilir kalır.

**Test:** Actions → "Altin arsivleyici" → Run workflow → `test_notify: true` → tek seferlik
test bildirimi.

### Actions cron ritmi

`archive.yml` cron'u `*/15` yazar; GitHub düşük aktiviteli repolarda zamanlanmış iş akışlarını
kısıtladığı için gerçekte **günde 10-17 çalışma** teslim edilir (aralar 1-3.5 saat). Sağlık
metrikleri bu gözlemlenen ritme göre kalibre edilmiştir
(`config.yaml alerts.archive_observed_freq_minutes: 90`); uyarı ancak kesinti 270 dk'yı aşınca çıkar.

### Actions dakika bütçesi

Repo **public** → Actions dakikası sınırsız. Ölçülen süreler: arşiv ~30 sn, günlük ~3 dk.
Repo private yapılırsa aylık 2000 dk sınırı devreye girer; o durumda sıklığı 30 dk'ya çekmek
(`config.yaml alerts.archive_freq_minutes: 30` + `archive.yml` cron `*/30`) bütçeyi ~1530 dk'ya
indirir.

### Sistemi duraklat / yeniden başlat

GitHub → Actions → ilgili workflow → "⋯" → Disable / Enable workflow. Bu hiçbir veriyi silmez.

---

## Prim z-skoru — arşiv birikimi

Prim z-skoru sistemin tek **kendi verisine bağımlı** sinyalidir: Kapalıçarşı priminin tarihsel
dağılımı hiçbir yerde satılmıyor, bu yüzden arşiv 7 Temmuz 2026'da sıfırdan başladı.

**Kapı gün sayar, kayıt değil.** Arşiv gün içinde ~10 örnek alır ve bunlar birbirinin tekrarıdır
(otokorelasyon); kayıt saymak bağımsız gözlem sayısını olduğundan büyük gösterir ve z-skoru
2 haftalık bir ortalamadan sapma ölçmeye indirger. `db.count_valid_prim_days()` yalnız geçerli
(hafta sonu ve `indicative` hariç) günleri sayar.

| | |
|---|---|
| Eşik | `config.yaml stats.zscore_min_samples: 60` gün |
| Kapı açılana kadar | Sinyal `veri_bekliyor`, rapor `⏳ arşiv birikiyor (N/60 gün)` yazar |
| Kapı açıldığında | Prim z-skor sinyali ve `z > 2` bildirimi kendiliğinden devreye girer — kod hazır, ek iş yok |

Haftalık pazar raporundaki "Arşiv İlerlemesi" satırı ilerlemeyi gösterir.

---

## Yerel çalıştırma (geliştirme ve on-demand analiz)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # doldur

.venv/bin/python -m pytest -q                 # 137 test
.venv/bin/python -m src.restore_db            # data/altin.sql → SQLite (tüm geçmiş arşiv)
.venv/bin/python -m src.evds_job backfill     # EVDS tarihsel (tek sefer)
.venv/bin/python -m src.history build         # tarihsel günlük ons×kur (2016+)
.venv/bin/python -m src.ohlc_hist backfill    # günlük OHLC (2016+, tek sefer)
.venv/bin/python -m src.report                # rapor + sinyaller + Telegram
```

### On-demand analiz komutları
```bash
.venv/bin/python -m src.history prim          # aylık külçe prim proxy + saflık tespiti
.venv/bin/python -m src.history quality       # eksik gün / aykırı değer taraması
.venv/bin/python -m src.backtest              # rejim + DCA + out-of-sample raporu
.venv/bin/python -m src.signals               # sinyal JSON (gerekçe+güven+geçersizlik)
.venv/bin/python -m src.signals alerts        # bildirim eşik değerlendirmesi
.venv/bin/python -m src.calculators 100000 12 30   # enstrüman net karşılaştırma
.venv/bin/python -m src.calculators bilezik 20 20  # bilezik başabaş
.venv/bin/python -m src.aipaket               # AI'a yapıştırılacak veri paketi + prompt
.venv/bin/python -m src.chart                 # destek/direnç + gösterge teyidi
.venv/bin/python -m src.chart validate        # grafik_dogrulama.md (yavaş, elle)
.venv/bin/python -m src.trends                # Google Trends kalabalık göstergesi
.venv/bin/python -m src.import_actions        # Actions CSV arşivini ana DB'ye aktar
```

**Telegram komutları:** `/durum` · `/rapor` · `/net <tutar> <ay> [altın%]` ·
`/bilezik <gram> <işçilik%>` · `/aipaket` · `/grafik`
(Actions push-only çalıştığı için bu komutlar yerelde `src.telegram_bot` açıkken yanıt verir.)

### ⚠️ Yerelde çalışmadan önce `git pull`
Sistem 15 dk'da bir repoya commit atıyor. Yerelde bir şey yapmadan önce **her seferinde `git pull`**
— yoksa push çakışır. (Workflow'lar `concurrency: repo-commit` + `pull --rebase` ile kendi
aralarında çakışmaz.)

> **Windows notu:** proje yolu non-ASCII karakter içeriyorsa `util.load_env()` SSL cacert'ini
> otomatik ASCII bir temp yola kopyalar (yfinance/curl_cffi düzeltmesi).

---

## Notlar / kısıtlar

- **Ons `GC=F` (futures):** spot XAU'ya göre ~%0.5-0.7 contango; primi hafif negatife iter.
- **EVDS servis yolu** 2024 sonrası `https://evds3.tcmb.gov.tr/igmevdsms-dis` (config'te).
- **Truncgil ToS'u yok** — kişisel kullanım (bkz. PROJE-REHBERI.md §1.4).

## Kanıt

`TESLIMAT.md` → `TESLIMAT-FAZ7.md` — her fazın testleri, DB satır sayıları, gerçek Telegram
mesajları, EVDS teyit tablosu, ölçüm sonuçları. Günlük kullanım için `İZLEME.md`.
