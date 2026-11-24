# Altın ve BIST hata denetimi — 2026-10-28

> Ekim 2026 çalışma kesiti. Sonraki üretim ve açık işler [STATE](../ai/STATE.md) ile [24 Kasım denetiminde](DENETIM-2026-11-24.md).

Mert'in talebiyle salt-okunur inceleme yapıldı. Kod, üretim verisi, workflow,
ödeme veya repo görünürlüğü değiştirilmedi. Çözüm için kullanıcı onayı bekleniyor.

- Actions oluşturma tarihi UTC bazında altın Eylül: 9/567; Ekim 1–28: 57/1000
  başarısız koşu. Ekim'de 43 nöbetçi ve 14 portföy koşusu başarısız. Mail,
  aynı Actions koşusunun bildirimi; ayrı bir kaynak hatası değil.
- **P2 — Doğrulandı:** 28 Ekim nöbetçisi yalnız `decision_data: GRAM` nedeniyle
  kırmızı. Aynı kayıtta kotasyon 1/1 geçerli; gerekçe geniş banka makası.
  `advisor/service.py:323` bunu veri engeline koyuyor;
  `advisor/watchdog.py:76` veri arızası yapıyor. Kayıtlı ask/bid makası %14,00656,
  eşik %3. Ekim'in 636 karar kaydında 59 veri bekleme var: 57 makas, 2 fiyat yok.
  Risk kapısı korunmalı; sınıflandırma ve Telegram/panel ifadesi ayrılmalı.
- Üretim commit'i `0cecf90869463693650c96f2a7eb2fd8a1f6ca0e`, gerçek aktif
  defter ve görünüm geçici kopyada ağsız tekrarlandı; aynı tek alarm üretildi.
  [Koşu](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/40690487498).
- **P2 — Doğrulandı:** 700 Ekim session_check kaydının 14'ünde banka kaynağı
  hatası var (13 ValueError, 1 ConnectionError). Payda seans dışı atlamaları da
  içerir; kaynak uptime oranı değildir. `advisor/service.py:219` yalnız istisna
  sınıfını sakladığından tam parser/HTTP nedeni DOĞRULANMADI.
- Altın çalışıyor olması BIST'in de çalıştığını kanıtlamıyor: BIST private ve
  ödeme/harcama engeliyle başlamıyor; son çevrim 23 Ekim 13:17 TR. BIST harici
  yedek kotası dolu ve TMSN 22 Ekim OHLC kaydı tutarsız. Bunlar farklı arızalar.
- İki ayarda ortak deney T0 `null`; beş deney kolu başlamamış. Eski ana hesap
  sonuçları yeni deneyin canlı kanıtı değildir.

Önerilen sıra: BIST işletim/kota engeli → iki depoda makas/veri sınıfları ve
güvenli kaynak tanısı/retry → doğrulanmış OHLC onarımı ve kapanış telafisi
tekrarı → onaylı yayın → taze çevrim, defter, Telegram ve harici yedek kabulü.
Silme, ödeme, üretim/veri onarımı ve yeni T0 ayrıca açık onaya bağlıdır.

Ortak ayrıntılı rapor aynı çalışma alanındaki BIST projesinde
`docs/HATA-DENETIMI-2026-10-28.md`; makbuzları `reports/actions-2026-10-28/`
altındadır. İki deponun incelenen 18 kod/config/workflow dosyası üretimle eşit.
BIST tarafında 14 mevcut davranış testi geçti; bu yeni düzeltme veya üretim
sağlığı kanıtı değildir. Kapanış telafisinin kök nedeni ve Billing alt nedeni açık.
