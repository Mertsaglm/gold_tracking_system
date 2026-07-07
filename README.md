# Altın Takip — MVP

Türkiye altın piyasası veri toplayıcı + **piyasa durum makinesi** + günlük markdown/Telegram raporu.
Kişisel araç; ücretsiz kaynaklar. **Hedef üretim ortamı: Oracle Cloud Always Free (Ubuntu).**
Windows yalnızca geliştirme/yerel test içindir.

> ⚠️ Genel bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.

## Ne yapar?

- **Kaynaklar:** Truncgil (60 sn, serbest piyasa gram/çeyrek/tam/Cumhuriyet + USD), yfinance (5 dk, ons XAU/USD + USD/TRY), TCMB EVDS (günlük; kur/faiz/TÜFE/altın/enflasyon beklentisi).
- **Arşiv:** ham tick + 1 dk OHLC → SQLite; EVDS 5 yıllık tarihsel seriler `evds_daily`.
- **Hesaplar:** teorik has gram, **prim** (saflık düzeltmeli), makas, çeyrek primi, **log-getiri dekompozisyonu** (ons/kur/prim), **dolar bazlı gram getirisi**, z-skor.
- **Durum makinesi:** her bacak `FRESH / STALE / CLOSED_WEEKEND / CLOSED_HOLIDAY`. Prim yalnız üç bacak FRESH iken **geçerli**; forex kapalıyken `indicative` (z-skor/backtest'ten dışlanır). Hafta sonu beklenti serisi + pazartesi mutabakatı.
- **Makro bağlam (EVDS):** politika faizi, net mevduat faizi, TÜFE, 12 ay enflasyon beklentisi, **reel net mevduat faizi**.
- **Gösterge uzlaşı paneli:** ABD 10Y reel faiz (FRED), DXY (FRED), ons 50/200 GMA (yfinance), TL reel net mevduat (EVDS), SPDR GLD tonaj — her biri olumlu/nötr/olumsuz + toplam uzlaşı skoru.
- **Rapor:** gün sonu markdown → dosya + Telegram (düz metin). Bot komutları: `/durum` (HTML), `/rapor`.
- **Loglama:** `logs/` altında dönen dosya logları (5 MB × 5).
- **Kapsama:** rapor "son 24s veri kapsaması %X, en uzun kesinti Y dk" satırı — çalışmadığı dönemler görünür; z-skor yalnız FRESH kayıtları sayar.

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
  evds_job.py        EVDS backfill + günlük güncelleme + rapor bağlamı
  reconcile.py       pazartesi hafta sonu mutabakatı
  report.py          gün sonu markdown raporu
  telegram_bot.py    gönderim + /durum /rapor (long-polling)
  logging_setup.py   dönen dosya logları
  supervisor.py      opsiyonel çapraz-platform watchdog (Oracle'da systemd bunu üstlenir)
  backup_db.py       güvenli SQLite dump (.backup API)
  evds_discover.py   EVDS kod keşfi
tests/               calc + durum makinesi + gösterge birim testleri (31 test)
deploy/              systemd .service / .timer (Oracle)
scripts/             backup.sh (Linux), backup.ps1 (Windows) — opsiyonel
```

## Yapılandırma

- `config.yaml`: tüm eşikler, URL'ler, seri kodları, oranlar. Kodda sabit yoktur.
- `.env` (`.env.example`'dan kopyala):
  - `EVDS_API_KEY` — https://evds2.tcmb.gov.tr → Profilim → API Key Kopyala
  - `TELEGRAM_BOT_TOKEN` — BotFather
  - `TELEGRAM_CHAT_ID` — @userinfobot

---

## Yerel çalıştırma (geliştirme — Windows/Linux)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # doldur

.\.venv\Scripts\python.exe -m pytest -q                 # 61 test
.\.venv\Scripts\python.exe -m src.evds_job backfill     # EVDS 10 yıl (tek sefer)
.\.venv\Scripts\python.exe -m src.history build         # tarihsel günlük ons×kur (2016+)
.\.venv\Scripts\python.exe -m src.backtest              # backtest_raporu.md
.\.venv\Scripts\python.exe -m src.collector             # toplayıcı (Ctrl+C durur)
.\.venv\Scripts\python.exe -m src.report                # rapor + sinyaller + Telegram
.\.venv\Scripts\python.exe -m src.telegram_bot          # bot (ayrı terminal)
```

### On-demand analiz komutları (7/24 gerektirmez)
```powershell
.\.venv\Scripts\python.exe -m src.history build         # history_daily (yfinance ons × EVDS kur)
.\.venv\Scripts\python.exe -m src.history prim          # aylık külçe prim proxy + saflık tespiti
.\.venv\Scripts\python.exe -m src.history quality       # eksik gün / aykırı değer taraması
.\.venv\Scripts\python.exe -m src.backtest              # rejim + DCA + out-of-sample raporu
.\.venv\Scripts\python.exe -m src.signals               # sinyal JSON (gerekçe+güven+geçersizlik)
.\.venv\Scripts\python.exe -m src.signals alerts        # bildirim eşik değerlendirmesi
.\.venv\Scripts\python.exe -m src.calculators 100000 12 30   # enstrüman net karşılaştırma
.\.venv\Scripts\python.exe -m src.calculators bilezik 20 20  # bilezik başabaş
.\.venv\Scripts\python.exe -m src.aipaket               # AI'a yapıştırılacak veri paketi + prompt
.\.venv\Scripts\python.exe -m src.trends                # Google Trends kalabalık göstergesi
.\.venv\Scripts\python.exe -m src.import_actions        # Actions CSV arşivini ana DB'ye aktar
```

**Telegram komutları:** `/durum` · `/rapor` · `/net <tutar> <ay> [altın%]` · `/bilezik <gram> <işçilik%>` · `/aipaket`

## GitHub arşivleyici (Actions — kesintisiz canlı arşiv)

Private repo: `.github/workflows/archive.yml` her 15 dk'da bir Truncgil + yfinance ons/kur çekip
`data/archive/YYYY-MM.csv`'ye ekler ve commit/push eder (GITHUB_TOKEN ile; **secret gömülmez**,
kaynaklar keysiz). Cron 5-30 dk gecikebilir (Actions kısıtı); timestamp çekim anından alınır.

- **Aktifleştirme:** repoyu push et → Actions sekmesinde workflow otomatik başlar (veya
  "Run workflow" ile elle tetikle). Repo Settings → Actions → Workflow permissions = "Read and write".
- **Ana DB'ye aktarma:** `python -m src.import_actions` — CSV'leri `ticks`(source='gh_actions') +
  `ohlc_1m` + `prim_history`'ye yazar. Hafta içi kayıtlar **geçerli** (z-skor arşivini doldurur),
  hafta sonu kayıtları `weekend=1` (pazartesi mutabakatı). Projenin ilk kesintisiz arşivi budur.
- **Oracle'a geçince:** çift veri olmaması için Actions workflow'unu kapat (Actions → Disable),
  canlı toplayıcı devralır.

Linux/macOS'ta `.venv/bin/python`.

> **Windows notu:** proje yolu non-ASCII ('altın') içerdiğinden `util.load_env()` SSL
> cacert'ini otomatik ASCII bir temp yola kopyalar (yfinance/curl_cffi düzeltmesi).
> Oracle'da (ASCII yol) bu devreye girmez.

---

## Oracle Cloud Always Free kurulumu (üretim — "bitmiş" hedef)

### Ortam seçimi
- **Bölge:** Frankfurt (veya en yakın). Ampere A1 kapasitesi bölgeye göre değişir; kapasite
  hatası alırsan bölge dene veya sırada bekle.
- **Shape (öncelik sırası):**
  1. **Ampere A1 (ARM64)** — 4 OCPU / 24 GB'a kadar Always Free. Tercih bu.
     Tüm bağımlılıkların ARM64 wheel'i var; derleme gerekmez.
  2. **A1 kapasitesi yoksa:** **VM.Standard.E2.1.Micro (AMD x86, Always Free)** — 1 OCPU / 1 GB.
     Bu proje için fazlasıyla yeter (tek DB, hafif polling).
- **OS:** Ubuntu 22.04/24.04 LTS.

### Kurulum
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git sqlite3

cd /home/ubuntu
git clone <repo-veya-scp-ile-kopyala> altin && cd altin
python3 -m venv .venv
.venv/bin/pip install -U pip && .venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env            # EVDS + Telegram doldur

.venv/bin/python -m pytest -q                # doğrula (61 test)
.venv/bin/python -m src.evds_job backfill    # EVDS tarihsel (tek sefer, ~7500 satır)
.venv/bin/python -m src.history build        # history_daily (backtest için, tek sefer)
.venv/bin/python -m src.backtest             # backtest_raporu.md (opsiyonel doğrulama)
.venv/bin/python -m src.evds_discover        # evds_series.json
```

### systemd servisleri
`deploy/*.service` içindeki `User=` / `WorkingDirectory=` yollarını kontrol et.
```bash
sudo cp deploy/altin-*.service deploy/altin-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now altin-collector.service   # sürekli toplayıcı (Restart=always)
sudo systemctl enable --now altin-bot.service         # Telegram botu
sudo systemctl enable --now altin-evds.timer          # günlük EVDS (15:30 UTC)
sudo systemctl enable --now altin-report.timer        # gün sonu raporu (15:45 UTC = 18:45 TR)

journalctl -u altin-collector.service -f              # canlı log
```
Oracle'da `Restart=always` çöken servisi tek başına toparlar — ayrı watchdog gerekmez
(`src/supervisor.py` yalnız systemd'siz ortam için opsiyoneldir).

---

## VM gelince taşınma (Windows'tan Oracle'a)

Şu an tüm kod + biriken veri bu Windows makinesinde. VM hazır olunca:

1. **Kodu taşı:** repoyu clone et (ya da klasörü `scp -r` ile kopyala). `.env`'i elle oluştur (git'te yok).
2. **DB'yi taşı (opsiyonel, geçmişi korumak için):** Windows'ta `python -m src.backup_db` ile
   `data/backups/altin_latest.sqlite` tutarlı kopyasını al, Oracle'da `data/altin.sqlite` olarak koy.
   İstemezsen EVDS backfill + sıfırdan tick toplama ile de başlayabilirsin.
3. **EVDS backfill + systemd** yukarıdaki gibi. Bitti.

---

## Yedekleme (opsiyonel — Oracle'a ertelendi)

Windows'ta 7/24 çalışılmadığı için acil değil. Oracle'da istenirse:
- `scripts/backup.sh` (Linux): güvenli `.backup` dump + private repoya `git push`.
- Etkinleştirmek için: private repo + push yetkisi (SSH deploy key/PAT), sonra
  `sudo systemctl enable --now altin-backup.timer`.
- Oracle blok depolama kalıcı olduğundan, VM'e güveniyorsan bu adımı hiç kurmadan da geçebilirsin.

## Notlar / kısıtlar

- **Ons `GC=F` (futures):** spot XAU'ya göre ~%0.5-0.7 contango; primi hafif negatife iter.
- **EVDS servis yolu** 2024 sonrası `https://evds3.tcmb.gov.tr/igmevdsms-dis` (config'te). Değerler nokta-ondalıklı.
- **Truncgil ToS'u yok** — kişisel kullanım (bkz. PROJE-REHBERI.md §1.4).
- Kapsam dışı (sonraki fazlar): sinyal/bildirim motoru (v2), backtest + AI sentez (v3).

## Kanıt

Bkz. `TESLIMAT.md` — testler, DB satır sayıları, gerçek Telegram mesajları, EVDS teyit tablosu + backfill, gösterge paneli, kapsama örneği, bilinen eksikler.
