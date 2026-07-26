# PROJECT.md — Projenin Kimliği

> Bir kez yazılır, nadiren değişir. Derin teknik detay için kök dizindeki
> **PROJE-REHBERI.md**, **README.md** ve **config.yaml**'a bak.

## Proje Adı
Altın Takip Sistemi (`gold_tracking_system`)

## Tek Cümlelik Amaç
Mert'in **elindeki gram sayısını artırmasına** yardım eden kişisel karar-destek
sistemi: Kapalıçarşı primini, makası ve göstergeleri otonom izler, her gün
**net bir hüküm** verir (bu ay ne kadar al · satılır mı), verdiği her hükmü
kaydedip **karnesini tutar**; GitHub Actions üstünde kendi kendine çalışır.

## Amaç Fonksiyonu (her hüküm buna karşı ölçülür)
**Terminal gram sayısı** — TL getirisi değil. Ölçüt gram olunca TL enflasyonu
artefaktı kendiliğinden ölür ve her iddia yanlışlanabilir olur: 100 gramla
başladın, 108 gram bitirdin → tuttu.

## Kapsam (Ne VAR)
- **Veri toplama:** Truncgil (gram/çeyrek/kur) + yfinance (ons XAU, GC=F OHLC) +
  TCMB EVDS (faiz/TÜFE) + FRED (reel faiz/DXY)
- **Depolama:** 15 dk CSV arşivi (`data/archive/`) + SQLite (diff'lenebilir
  dump `data/altin.sql`)
- **Hesap:** teorik has gram, prim %, makas %, prim z-skoru (60 gün kapısı),
  ATR, çeyrek primi
- **Bildirim:** eşik-tabanlı anomali (24s soğuma + günlük tavan), hafta sonu
  beklentisi; üç bacak FRESH değilse anomali bastırılır
- **Rapor:** günlük (18:35 TR) + pazar haftalık; grafik yorumu (destek/direnç +
  gösterge teyidi)
- **Telegram bot komutları:** `/durum` `/rapor` `/net` `/bilezik` `/grafik` `/aipaket`

## Kapsam Dışı (Ne YOK)
- **Üçüncü kişilere** yatırım tavsiyesi / danışmanlık servisi. Sistem Mert'in
  **kişisel** karar-destek aracıdır; kendisine net hüküm verir ve o hükmün
  karnesini tutar. Disclaimer satırı kalır (maliyeti sıfır) ama çıktıyı
  sulandırmaz — dürüstlük hedge dilinden değil KARNEDEN gelir (ADR #007).
- Otomatik alım-satım / emir iletimi
- Ayrı sunucu / 7x24 servis — **şimdilik** yok, üretim GitHub Actions cron.
  Oracle Cloud'a geçiş düşünüldü ama **ertelendi (iptal değil)**; masada duran bir
  seçenek. Bu yüzden `deploy/` systemd dosyaları ve `runtime_mode: collector`
  silinmez — o senaryonun hazır altyapısıdır.

## Kısıtlar
- **Bütçe:** ücretsiz kalmalı — üretim GitHub Actions (public repo, sınırsız dk)
- **Ortam:** Python 3.12; yerel geliştirme macOS (Apple Silicon); üretim ubuntu-latest
- **Araç-bağımsızlık:** Claude Code aboneliği bitince Codex/Antigravity/GLM/Kiro/
  VSCode ile devam edilecek → araç-özel çözümden kaçın (bkz DECISIONS #001, #002)
- **Veri kalitesi:** Actions cron throttling → 15 dk hedefinin ~%62-75'i
  gerçekleşiyor (sistem tolere ediyor; z-skor yalnız FRESH kayıt sayar)

## Teknoloji Yığını
| Katman | Seçim |
|---|---|
| Dil | Python 3.12 (harici bağımlılık minimal: requests, PyYAML, yfinance) |
| Veri | SQLite + aylık CSV arşiv |
| Kaynaklar | Truncgil · yfinance · TCMB EVDS · FRED |
| Çalışma | GitHub Actions — `archive.yml` (*/15 dk), `daily.yml` (15:35 UTC) |
| Bildirim | Telegram Bot API (saf `requests`) |

## Başarı Kriteri
Doğru ölçülmüş prim/z-skor, güvenilir günlük rapor ve düşük yanlış-alarmlı
bildirim; sistem elle müdahale olmadan günlerce çalışmaya devam ediyor.
