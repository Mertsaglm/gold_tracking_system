# Altın Takip — MVP Faz 1

Türkiye altın piyasası veri toplayıcı + **piyasa durum makinesi** + günlük markdown raporu + Telegram botu.
Kişisel araç; ücretsiz kaynaklar; hedef ortam Oracle Cloud Always Free (Ubuntu ARM).

> ⚠️ Genel bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.

## Ne yapar?

- **Truncgil** (60 sn) serbest piyasa gram/çeyrek/tam/Cumhuriyet + USD; **yfinance** (5 dk) ons (XAU/USD) + USD/TRY; **EVDS** (günlük) resmi kur/faiz/TÜFE/altın serileri.
- Ham tick + 1 dk OHLC → SQLite.
- **Prim** (saflık düzeltmeli, `gram-has-altin` üzerinden), **makas**, **çeyrek primi**, **log-getiri dekompozisyonu** (ons/kur/prim ayrıştırma).
- **Durum makinesi:** her bacak `FRESH / STALE / CLOSED_WEEKEND / CLOSED_HOLIDAY`. Prim yalnız üç bacak da FRESH iken **geçerli**; forex kapalıyken `indicative` → z-skor/backtest serisinden dışlanır. Hafta sonu sapması ayrı tabloda; pazartesi mutabakat job'ı.
- Gün sonu raporu → dosya + Telegram. Bot komutları: `/durum`, `/rapor`.
- Günlük SQLite yedeği → private GitHub reposuna otomatik push.

## Proje yapısı

```
config.yaml          tüm eşik/URL/oran (kod içine sabit gömülmez)
holidays_tr.yaml     TR/US tatil takvimi (yılda bir güncelle)
.env                 EVDS + Telegram kimlikleri (git'e girmez)
evds_series.json     keşif çıktısı (evds_discover ile üretilir)
src/
  util.py            TR sayı ayrıştırma, zaman, config/env
  calc.py            teorik gram, prim, makas, çeyrek primi, dekompozisyon, z-skor
  market_calendar.py forex seansı + tatil + gündüz/gece
  state_machine.py   FRESH/STALE/CLOSED_* + prim geçerliliği
  db.py              SQLite şema + erişim
  sources/           truncgil.py, yf.py, evds.py
  collector.py       ana döngü
  reconcile.py       pazartesi mutabakat
  report.py          gün sonu markdown raporu
  telegram_bot.py    gönderim + /durum /rapor (long-polling)
  evds_discover.py   EVDS kod keşfi (kurulumun parçası)
tests/               calc + durum makinesi birim testleri
deploy/              systemd .service / .timer
scripts/backup.sh    yedek + git push
```

---

## Yerel çalıştırma (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # EVDS + Telegram doldur (opsiyonel; boşsa o kaynak atlanır)

# testler
.\.venv\Scripts\python.exe -m pytest -q

# toplayıcı (Ctrl+C ile durur)
.\.venv\Scripts\python.exe -m src.collector

# rapor üret (+ Telegram doluysa gönderir)
.\.venv\Scripts\python.exe -m src.report

# Telegram botu (ayrı terminal)
.\.venv\Scripts\python.exe -m src.telegram_bot

# EVDS kod keşfi (key gerekli)
.\.venv\Scripts\python.exe -m src.evds_discover
```

Linux/macOS'ta `.venv/bin/python` kullanın.

---

## Oracle Cloud Always Free (Ubuntu, ARM) kurulumu

Ampere A1 (ARM64) instance. Tüm bağımlılıklar saf-Python veya ARM wheel'i olan paketler; **ARM'de sorunsuz** (yfinance/pandas/numpy ARM64 wheel'leri mevcut, derleme gerekmez).

### 1. Sistem hazırlığı

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git sqlite3
```

### 2. Repo + venv

```bash
cd /home/ubuntu
git clone git@github.com:KULLANICI/altin.git altin   # private repo (yedekle aynı repo)
cd altin
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env                      # EVDS + Telegram doldur
```

### 3. Doğrulama

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m src.evds_discover                  # evds_series.json üretir
```

### 4. systemd servisleri

`deploy/*.service` içindeki `User=` ve `WorkingDirectory=` yollarını kendi kullanıcına göre kontrol et.

```bash
sudo cp deploy/altin-*.service deploy/altin-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now altin-collector.service    # sürekli toplayıcı
sudo systemctl enable --now altin-bot.service          # Telegram botu
sudo systemctl enable --now altin-report.timer         # gün sonu raporu
sudo systemctl enable --now altin-backup.timer         # yedek + push

# durum
systemctl status altin-collector.service
journalctl -u altin-collector.service -f
```

Sunucu saati UTC ise timer'lar 17:00/17:15 UTC = 20:00/20:15 TR'ye ayarlı. TR saati kullanıyorsan `OnCalendar` değerlerini güncelle.

### 5. Yedekleme (git push)

`backup.sh` private repoya push eder — **arşiv tek kopya bırakılmaz.** Kurulumda:

```bash
git remote -v                          # origin private repo olmalı
git config user.email "bot@local"
git config user.name "altin-bot"
# SSH deploy key veya PAT ile push yetkisi verilmiş olmalı
chmod +x scripts/backup.sh
```

`data/` ve `reports/` `.gitignore`'da **tutulur** (yedeklenir); sadece WAL/SHM geçici dosyaları hariç.

---

## Notlar / kısıtlar

- **Ons kaynağı `GC=F` (futures):** spot XAU'ya göre ~%0.5-0.7 contango taşır, primi hafif negatife iter. Spot feed'e geçilince prim sıfıra yaklaşır. Ücretsiz spot alternatifi sınırlı; MVP'de futures proxy kabul edildi.
- **Truncgil ToS'u yok:** kişisel kullanım için. Ürünleşirse yazılı izin/lisanslı kaynak gerekir (bkz. PROJE-REHBERI.md §1.4).
- **yfinance** resmî API değil; kırılırsa `src/sources/yf.py` tek noktadan güncellenir.
- Kapsam dışı (sonraki fazlar): sinyal/bildirim motoru, backtest, AI katmanı, web/mobil arayüz.

## Kanıt / doğrulama

Bkz. `TESLIMAT.md` — 16 dk yerel sürüş çıktısı, SQLite örnek satırlar, üretilmiş rapor, saflık düzeltmesi ölçümü.
