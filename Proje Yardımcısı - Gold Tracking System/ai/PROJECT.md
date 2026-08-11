# PROJECT.md — Projenin Kimliği

> Kararlı içerik: bir kez yazılır, nadiren değişir. Bu yüzden devir paketinde
> tutulur. **Kanonik kopya `../../ai/PROJECT.md`'dir**; ikisi çelişirse kök geçerlidir.
> Derin teknik detay: `../../README.md`, `../../config.yaml`.
> ⚠️ `../../PROJE-REHBERI.md` yalnız **inşa dönemini (Faz 1-7)** kapsar — karar
> motoru orada YOKTUR; onun için `../../ai/DECISIONS.md` #007/#008.
>
> _Yeni bir projeye tohumlarken `yeni-proje.sh` bu dosyayı boş şablonla değiştirmez —
> yeni projede içeriği silip `/tanis` ile yeniden doldurt._

## Proje Adı
Altın Takip Sistemi (`gold_tracking_system`) · https://github.com/Mertsaglm/gold_tracking_system

## Tek Cümlelik Amaç
Mert'in **elindeki gram sayısını artırmasına** yardım eden kişisel karar-destek
sistemi: primi, makası ve göstergeleri otonom izler, her gün **net bir hüküm**
verir (bu ay ne kadar al · satılır mı), verdiği her hükmü kaydedip **karnesini
tutar**; GitHub Actions üstünde kendi kendine çalışır.

## Amaç Fonksiyonu (her hüküm buna karşı ölçülür)
**Terminal gram sayısı** — TL getirisi değil. Ölçüt gram olunca TL enflasyonu
artefaktı kendiliğinden ölür ve her iddia yanlışlanabilir olur (ADR #007-A).

## Kapsam (Ne VAR)
- **Veri toplama:** Truncgil (gram/çeyrek/kur) + yfinance (ons XAU, GC=F OHLC) +
  TCMB EVDS (faiz/TÜFE) + FRED (reel faiz/DXY — *şu an ölü, aşağıya bak*)
- **Depolama:** ~90 dk'da bir CSV arşivi (`data/archive/`) + SQLite
  (diff'lenebilir metin dump `data/altin.sql`)
- **Hesap:** teorik has gram, prim %, makas %, prim z-skoru (60 **gün** kapısı),
  ATR, çeyrek primi z-skoru
- **Bildirim:** eşik-tabanlı anomali (24s soğuma + günlük tavan 6), hafta sonu
  beklentisi; üç bacak FRESH değilse anomali bastırılır
- **Rapor:** günlük (18:35 TR) + pazar haftalık; grafik yorumu (destek/direnç +
  gösterge teyidi)
- **Denetim izi:** giden her Telegram mesajı `data/telegram_outbox.jsonl`'a,
  z-skor kuru provası `data/zskor_prova.jsonl`'a yazılır
- **Karar:** raporun EN BAŞINDA **HÜKÜM** — iki kol: ÇEKİRDEK (aylık alım
  şiddeti, **açık, birincil**) + TAKTİK (sat/geri al, **doğuştan kapalı** kapı).
  Ölçüldü: satmak 1 ayda ortalama **−1.99% gram** kaybettiriyor (ADR #007-B).
- **Karne:** verilen her hüküm `predictions`'a **değiştirilemez** yazılır (SQLite
  trigger), vadesi gelince gram uzayında çözülür. ⚠️ Bugün karne "tabana fark" ve
  "gram etkisi" ÜRETEMİYOR ve bunu açıkça yazıyor — aşağıya bak.
- **Telegram bot komutları:** `/hukum` `/karne` `/durum` `/rapor` `/net`
  `/bilezik` `/grafik` `/aipaket` — ⚠️ yalnız yerelde `src.telegram_bot` açıkken
  yanıt verir; üretim (Actions cron) **push-only**, gelen komutu okumaz.

## Kapsam Dışı (Ne YOK)
- **Yatırım tavsiyesi** — her rapor "genel bilgilendirme amaçlıdır" ile biter
- **Otomatik alım-satım / emir iletimi**
- **Ayrı sunucu / 7x24 servis** — şimdilik yok, üretim GitHub Actions cron.
  Oracle Cloud'a geçiş düşünüldü ama **ertelendi (iptal DEĞİL)**. Bu yüzden
  `deploy/` systemd dosyaları ve `runtime_mode: collector` **silinmez** —
  o senaryonun hazır altyapısıdır (bkz. LESSONS L-006).
- **Uydurma gösterge** — verisi gelmeyen gösterge paydadan düşer. Reel faiz için
  bilerek yedek konulmadı: `^TNX` nominaldir, TIPS reel getirisi değil.

## Kısıtlar
- **Bütçe:** ücretsiz kalmalı — üretim GitHub Actions (public repo, sınırsız dk)
- **Ortam:** Python 3.12; yerel geliştirme macOS (Apple Silicon); üretim ubuntu-latest
- **Araç-bağımsızlık:** Claude Code aboneliği bitince Codex/Antigravity/GLM/VSCode
  ile devam edilecek → araç-özel çözümden kaçın (bkz. `DECISIONS.md` #001, #002)
- **Veri kalitesi:** GitHub Actions cron throttling → `*/15` yazar ama gerçekte
  **~13 çalışma/gün** teslim eder. Platform kısıtı, ücretsiz düzeltilemez; sağlık
  metrikleri buna göre kalibre (`archive_observed_freq_minutes: 90`).
- **Gizlilik:** repo **public** — `.env`, `ai/PROFILE.md` ve Telegram export'u
  gitignore'da. `data/` ve `reports/` bilerek izlenir (yalnız fiyat verisi/analiz).

## Teknoloji Yığını
| Katman | Seçim |
|---|---|
| Dil | Python 3.12 (bağımlılık minimal: requests, PyYAML, yfinance) |
| Veri | SQLite + aylık CSV arşiv; binary yerine metin dump commit'lenir |
| Kaynaklar | Truncgil · yfinance · TCMB EVDS · FRED |
| Çalışma | GitHub Actions — `archive.yml` (`*/15`), `daily.yml` (15:35 UTC) |
| Bildirim | Telegram Bot API (saf `requests`, harici kütüphane yok) |
| Test | pytest — **800+ test** (2026-07-27); sözleşme kilidi, bkz. kök `ai/DECISIONS.md` #009 |

## Bu projenin çalışma kültürü (Usta bunu bilmeli)
Bu proje **ölçüm kültürü** üzerine kurulu. Faz 3'te backtest metodolojisi
düzeltilince "rejim üstünlüğü" ve "prim-koşullu DCA" iddiaları **geri çekildi**;
Faz 6'da destek/direnç seviyelerinin **yön kenarı olmadığı** ölçülüp raporun diline
işlendi. Kural: **iddia ham tabana karşı ölçülür, çıkmazsa geri çekilir ve
saklanmaz.** Zayıf N, büyük farkı ezer. Kanıt: `../../docs/TESLIMAT-ARSIV.md`.

## Başarı Kriteri
Doğru ölçülmüş prim/z-skor, güvenilir günlük rapor ve düşük yanlış-alarmlı
bildirim; sistem elle müdahale olmadan günlerce çalışmaya devam ediyor.

## Bilinen açık noktalar (2026-07-27)
- **Karne ÖLÇÜM ÜRETEMİYOR — en önemlisi budur.** Taktik kapı kapalıyken kol
  yalnız `TUT`, çekirdek kol yalnız `AL_*` üretiyor; `gram.hukum_dogru_mu`
  bunların hepsine tabanla (`TUT`) aynı cevabı verdiği için "tabana fark" ve
  "gram etkisi" piyasa ne yaparsa yapsın **yapısal olarak 0.00** çıkıyor. Kapı
  da açılma şartı olarak tam bu iki sayıyı okuyor → kendi kendini kilitliyor.
  Sistem artık bunu **söylüyor** ("ÖLÇÜM İÇERMİYOR") ama döngü **KIRILMADI**;
  kırmak için gölge kol gerekiyor, o karar ~Ekim 2026'ya bırakıldı
  (ADR #008-B · ders **L-010**).
- **FRED ölü** (2026-07-07'den beri) → DXY yfinance `DX-Y.NYB` yedeğine düşüyor;
  reel faiz göstergesi kapalı (yedeksiz, bilerek). **Google Trends de 12/14 gün
  ölü** (pytrends 429) → panel fiilen **5/7** göstergeyle çalışıyor
  (ölçüldü 2026-07-29, son 14 rapor).
- **Prim + çeyrek z-skoru kapalı** — 60 günlük kapı ~**14 Eylül 2026**'da açılacak.
  Kapı açılmadan z tabanı (kayıt mı gün mü) kararlaştırılmalı; kuru prova bunun
  için her gün ölçüm biriktiriyor. Ayrıntı ve tarihler: `../../ai/STATE.md` → TAKVİM.
