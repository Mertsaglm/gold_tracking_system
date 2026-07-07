# TESLIMAT — MVP Faz 1 Kanıt Dosyası

Tarih: 2026-07-07 · Ortam: Windows (yerel), Python 3.12.4, .venv

## Özet

| Kalem | Durum |
|---|---|
| Veri toplayıcı (Truncgil 60sn + yfinance 5dk) | ✅ 16 dk kesintisiz çalıştı (exit 0) |
| Piyasa durum makinesi (FRESH/STALE/CLOSED_*) | ✅ çalışıyor, 17 kayıt GEÇERLİ etiketli |
| Hesap katmanı (prim/makas/çeyrek/dekompozisyon/z-skor) | ✅ + 22 birim testi geçti |
| Gün sonu markdown raporu | ✅ üretildi (`reports/rapor_2026-07-07.md`) |
| Telegram gönderimi | ⚠️ kod hazır; gerçek gönderim token gerektirir (aşağıda) |
| SQLite arşiv + OHLC | ✅ 127 tick, 127 OHLC, 17 prim |
| Yedek + git push | ✅ script hazır; repo init + commit yapıldı |
| systemd deploy dosyaları + README (ARM) | ✅ |

---

## 1. Birim testleri (22/22 geçti)

```
$ .venv/Scripts/python.exe -m pytest -q
......................                        [100%]
22 passed in 0.06s
```

Kapsam: teorik gram, **saflık düzeltmesi (~%0.5)**, makas, **çeyrek primi has içeriği**,
**dekompozisyon toplamı (tam eşitlik)**, dekompozisyon = gram log-getirisi, z-skor
(yetersiz/ok/flat), **forex seansı** (hafta içi/Cumartesi/Cuma gecesi/Pazar akşamı),
**bacak durum geçişleri** (FRESH/STALE/CLOSED_WEEKEND/NO_DATA), **prim geçerliliği**
(hafta sonu → indicative), **TR tatil** ve **gündüz/gece** tespiti.

## 2. 16 dakikalık yerel sürüş

```
18:32:13 Toplayıcı başladı. Truncgil 60s, yfinance 300s.
18:32:14 yfinance: ons=4156.60 usdtry=46.836
18:32:14 prim=-0.823% (naive=-0.324) makas=0.015 ceyrek_prim=-0.08 [GECERLI tum_bacaklar_taze]
...
18:48:28 prim=-0.668% (naive=-0.169) makas=0.015 ceyrek_prim=-0.17 [GECERLI tum_bacaklar_taze]
18:48:28 max_seconds doldu, çıkılıyor.
```

DB sayımları: **ticks=127, ohlc_1m=127, prim_history=17, weekend_expectation=0**
(hafta içi olduğu için hafta sonu tablosu boş — beklenen).

### Örnek tick satırları (SQLite)

```
15:48:28 truncgil cumhuriyet      alis=41609.0  satis=42239.0
15:48:28 truncgil tam             alis=40075.01 satis=40874.55
15:48:28 truncgil ceyrek          alis=10018.75 satis=10249.98
15:48:28 truncgil gram_has_altin  alis=6212.35  satis=6213.29
15:48:28 truncgil gram_altin      alis=6243.56  satis=6244.51
```

### Örnek prim satırları

```
15:48:28 ons=4154.2 kur=46.833 teorik=6255.1 piyasa=6213.3 prim=-0.668% naive=-0.169% makas=0.015% ceyrek=-0.17% ind=0
15:46:26 ons=4155.6 kur=46.834 teorik=6257.3 piyasa=6213.3 prim=-0.703% naive=-0.204% makas=0.015% ceyrek=-0.17% ind=0
```

### 1 dk OHLC (gram_has_altin)

```
15:48 O=6213.29 H=6213.29 L=6213.29 C=6213.29 n=1
15:47 O=6213.29 H=6213.29 L=6213.29 C=6213.29 n=1
```

## 3. İstenen doğrulamalar

### Prim ±%3 bandında mı? → ✅ EVET

Tüm kayıtlar -0.67% … -0.82% aralığında. Rapor otomatik "✅ Prim ±%3 makul bandında" yazıyor.

> Not: ons kaynağı `GC=F` (futures) spot XAU'ya göre ~%0.5-0.7 contango taşıdığı için
> prim hafif negatif. Spot feed'e geçilince sıfıra yaklaşır. Mantık doğru çalışıyor.

### Saflık düzeltmesi ~%0.5 fark yaratıyor mu? → ✅ EVET (0.498 puan)

17 kayıt ortalaması:
```
ort prim(has, düzeltmeli) = -0.788%
ort prim(naive, perakende) = -0.289%
FARK = 0.498 puan   ← ~%0.5, beklenen
```
Kaynak: `gram-has-altin` (saf, 6213.29) ile `gram-altin` (perakende, 6244.51) oranı = 0.995.
Prim'i `gram-altin` ile (naif) hesaplarsan gerçek primi ~0.5 puan yüksek görürsün — düzeltme bunu kaldırıyor.

### Dekompozisyon gerçek veride tutarlı mı? → ✅ EVET

16 dk içindeki gram TL hareketi (+0.092%) ayrıştırması:
```
Ons  katkısı : -0.0578%
Kur  katkısı : -0.0060%
Prim katkısı : +0.1560%
TOPLAM       : +0.0923%
bileşen toplamı == total (fark < 1e-9) ✅
```

## 4. Üretilen rapor

`reports/rapor_2026-07-07.md` — fiyat özeti, prim/makas (saflık etkisi satırı dahil),
dekompozisyon (24s veri yokken doğru şekilde "yetersiz geçmiş" diyor), veri kalitesi
(z-skor 17/60 → "yetersiz veri", tam istendiği gibi), feragatname. Tam metin dosyada.

## 5. Telegram

- `/durum` mesajı canlı DB'ye karşı render edildi (biçim doğrulandı):

```
*Anlık Durum* (18:33 TR) 🟢 geçerli
Ons: `4156.60$`  ·  USD/TRY: `46.8360`
Teorik has gram: `6259.06₺`
Piyasa has gram: `6207.56₺`
*Prim: -0.823%*  ·  Makas: 0.015%
Çeyrek primi: -0.08%
_tum_bacaklar_taze_
```

- **Gerçek gönderim** senin bot token'ını gerektiriyor (`.env` şu an boş). Token ekleyince tek komutla test:

```bash
# .env içine TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID yaz, sonra:
.venv/Scripts/python.exe -m src.report          # raporu üretir + Telegram'a gönderir
.venv/Scripts/python.exe -m src.telegram_bot     # /durum ve /rapor komutlarını dinler
```

Rapor kodu token yokken düzgünce atlıyor (log: `telegram gönderim hata: TELEGRAM_CHAT_ID
tanımlı değil` → çökme yok, dosya yine yazıldı).

## 6. Bilinen sınırlar / sonraki adım

- Ons futures proxy (yukarıda). Ücretsiz spot XAU alternatifi ararsan `src/sources/yf.py` tek noktadan değişir.
- EVDS keşif + günlük çekim key gerektirir; key yoksa sessizce atlanıyor (test edildi).
- Kapsam dışı (v2/v3): sinyal/bildirim motoru, backtest, AI katmanı, web arayüz.

## Tekrar üretmek için

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest -q
# 16 dk sürüş:
.venv/Scripts/python.exe -c "from src import util,collector; util.load_env(); collector.run(util.load_config(), max_seconds=960)"
.venv/Scripts/python.exe -m src.report
```
