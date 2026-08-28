# Altın Takip

Türkiye altın piyasası veri toplayıcı + **piyasa durum makinesi** + günlük markdown/Telegram raporu.
Kişisel araç; ücretsiz kaynaklar.

**Üretim ortamı: GitHub Actions.** Sistem 7/24 kendi kendine çalışır — veri çeker, eşikleri
değerlendirir, Telegram'a rapor ve bildirim gönderir, arşivi repoya commit'ler. Kullanıcının
hiçbir şey çalıştırması gerekmez. Yerel kurulum yalnızca geliştirme ve on-demand analiz içindir.

> ⚠️ Genel bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.

## Ne yapar?

- **Kaynaklar:** Truncgil (serbest piyasa gram/çeyrek + USD **+ ons spot**;
  tam/Cumhuriyet çekilir ama arşive yazılmaz — `archive_fetch.FIELDS`),
  yfinance (**yalnız USD/TRY** — ons için bilerek kullanılmıyor, ADR #013),
  TCMB EVDS (günlük; kur/faiz/TÜFE/altın/enflasyon beklentisi).

  🔴 **AÇIK SORUN — prim bugün ölçüm taşımıyor (ADR #014).** Ons ile gramın
  ikisi de Truncgil'den gelince ons prim formülünde **cebirsel olarak
  sadeleşiyor**; geriye satıcının kendi saflık çarpanı kalıyor. Ölçüldü
  (2026-08-28, 934 kayıt): 08-17 sonrası prim'in **%99.81'i** yalnız iki USD
  beslemesinin oranı (düzeltme öncesi %18.2). Sistem bunu **bağımsızlık
  nöbetçisi** ile her gün tespit ediyor, o günleri kapı sayacının dışına alıyor
  ve raporun en üstüne kırmızı satır basıyor. Kalıcı çözüm bağımsız bir spot ons
  kaynağı gerektiriyor — karar bekliyor.
- **Arşiv:** ham tick + 1 dk OHLC → SQLite; EVDS tarihsel seriler `evds_daily`; günlük gerçek OHLC
  `ohlc_daily` (2016+).
- **Hesaplar:** teorik has gram, **prim** (saflık düzeltmeli), makas, çeyrek primi, **log-getiri
  dekompozisyonu** (ons/kur/prim), **dolar bazlı gram getirisi**, z-skor.
- **Durum makinesi:** her bacak `FRESH / STALE / CLOSED_WEEKEND / CLOSED_HOLIDAY`. Prim yalnız üç
  bacak FRESH iken **geçerli**; forex kapalıyken `indicative` (z-skor/backtest'ten dışlanır).
  Hafta sonu beklenti serisi + pazartesi mutabakatı.
- **Bağımsızlık nöbetçisi (ADR #014):** prim iki **bağımsız** fiyatın farkıdır.
  Her gün gün-içi `piyasa/teorik` oranının değişim katsayısı ölçülür (iki bacak da
  aynı satıcıdan); eşiğin (`stats.bagimsizlik_cv_esigi: 1e-4`) altındaysa o günün
  kayıtları `indicative=1` + `reason='turetilmis'` işaretlenir → **kapı sayacına
  girmez**. Kayıt silinmez. Eşik iki ölçülmüş rejim arasındaki boşluğa oturur
  (gerçek min 2.97e-04 · kimlik max 5.50e-05), veriye uydurulmadı.
- **Makro bağlam (EVDS):** politika faizi, net mevduat faizi, TÜFE, 12 ay enflasyon beklentisi,
  **reel net mevduat faizi**.
- **Gösterge uzlaşı paneli:** ABD 10Y reel faiz (FRED), DXY (FRED → yedek yfinance
  `DX-Y.NYB`), ons 50/200 GMA (**`ohlc_daily`'den — canlı/kapanmamış bar DEĞİL**,
  ADR #014), TL reel net mevduat (EVDS), SPDR GLD tonaj,
  Google Trends — her biri olumlu/nötr/olumsuz + toplam uzlaşı skoru. Verisi gelmeyen
  gösterge **paydadan düşer** (uydurma yapılmaz); reel faiz için bilerek yedek
  konulmadı — `^TNX` nominal getiridir, TIPS reel getirisi değil.
  Panel bir rapor akışında **tek kez** hesaplanır (`_PANEL_CACHE`): eskiden iki
  tüketici ayrı ayrı çekiyordu ve 48 raporun 7'sinde iki payda farklı çıkmıştı,
  ikisinde etiket bile zıttı (ADR #014).
  ⚠️ Payda hâlâ **cevap veren gösterge sayısı** — bu yüzden uzlaşı skoru
  günler arası doğrudan kıyaslanamaz. Sabit paydaya geçmek etiket tanımını
  değiştirir; karar bekliyor.
- **Rejim sinyali — dejenerelik kapısı (ADR #014):** rejim = ons 200GMA × reel
  faiz trendi × kur oynaklığı. FRED DFII10 ölü olduğu için sınıflandırıcı
  **2585/2585 güne aynı etiketi** veriyordu; yani "rejim" tüm verinin, tabanın
  kendisiydi ve rapor bunu 48/48 gün bir ölçüm gibi basıyordu (`_baseline` ile
  birebir aynı satır). Artık sınıflandırıcı tek sınıfa çökerse sinyal
  **"ölçemedim"** der ve sebebini yazar. FRED dönerse kendiliğinden açılır.
- **Grafik yorumu:** gerçek günlük OHLC üzerinde fraktal swing pivot → ATR ölçekli kümeleme ile
  **destek/direnç bantları**, dönemsel zirve/dip, RSI/Bollinger/trend yapısı ile **çapraz teyit
  çetelesi**. Seviyeler ons USD'de hesaplanır, TL'ye **bugünkü kurla izdüşüm** olarak çevrilir.
  Ölçüm sonucu: seviyelerin yön üstünlüğü yok — kademe/stop planlaması için sunulur, yön iddiası
  olarak değil (ölçüm: `docs/TESLIMAT-ARSIV.md` → Faz 6).
  **2026-07-29 tazelendi (ADR #010-A):** taban artık TÜM fazlardan ölçülüyor ve eşik faz
  yayılımının altına inemiyor. 54 karşılaştırmada "zayıf kanıt" satırı **10 → 1** düştü;
  9'u yalnız pencere hizasından doğan artefaktmış. Grafiğin **ölçülmüş yön kenarı yok**.
- **Karar:** raporun en başında **HÜKÜM** — bu ay ne kadar al (çekirdek) + satılır
  mı (taktik, doğuştan kapalı kapı). Amaç fonksiyonu **terminal gram sayısı**;
  ölçüm `reports/gram_engeli.md`. Bkz. `ai/DECISIONS.md` #007.
  ✅ **Çekirdek kademesi 2026-08-11'de KAPATILDI (ADR #012)** — hüküm artık daima
  `NORMAL AL` (1.00×); alım planına dokunulmuyor. Kapatma gerekçesi ölçüm:
  kademeyi üreten `reel_mevduat > %10` kuralı ateşlendiğinde ertelemenin ortalama
  gram kazancı **%-0.64** (N=22, t=1.03) — başa baş **0.00**'ın ALTINDA, yani
  örneklem-**içi** (en iyimser) ölçümde bile gram kaybettiriyor. Canlı
  örneklem-dışı doğrulama (2026-07-27 → 08-10, gram +%9.55): **-%1.55 gram**.
  Mekanizma silinmedi, `karar.cekirdek.kademe_aktif: false` kapısına bağlandı;
  açılma şartı config'te kayıtlı (**N≥30 ve |t|≥2 ile +1.99p**). Kural yine
  değerlendirilir ve hüküm bloğu "kademe açık olsaydı 0.75× olurdu" diye yazar.
  İki eşik `reports/gram_aday_taramasi.md`'de ayrı sütun — taktik makas öder
  (+3.18p), çekirdek ödemez (+1.99p).
- **Karne:** verilen her hüküm `predictions` tablosuna **değiştirilemez** yazılır
  (SQLite trigger), vadesi gelince gram uzayında otomatik çözülür. `/karne` ile
  okunur.
  ⚠️ **Bugün karne "tabana fark" ve "gram etkisi" ÜRETEMEZ** ve bunu açıkça yazar:
  taktik kapı kapalıyken kol yalnız `TUT`, çekirdek kol yalnız `AL_*` üretiyor;
  `gram.hukum_dogru_mu` bunların hepsine tabanla (`TUT`) aynı cevabı verdiği için
  o iki sayı piyasa ne yaparsa yapsın **yapısal olarak 0.00** çıkar. Ölçüm değil,
  kimlik. Bkz. `ai/DECISIONS.md` #008 — kapıyı açacak gölge kol henüz yok.
- **Grafik:** 4 panel PNG (ons mum + destek/direnç · gram TL çizgi · iki motor ·
  RSI) günlük raporun ardından Telegram'a gider. `/grafik` görsel + metin döner.
  Gram paneli **çizgidir**: gram TL için OHLC türetilmez (bkz. `db.py` şeması).
- **Rapor:** gün sonu markdown → dosya + Telegram. Bot komutları: `/hukum`, `/durum`, `/rapor`.
- **Loglama:** `logs/` altında dönen dosya logları (5 MB × 5).
- **Kapsama:** rapor "son 24s veri kapsaması %X" satırı; **prim boşluğu** (kaynak boş dönerse de
  büyür) ile **çekim boşluğu** (Actions gerçekten durdu mu) ayrı raporlanır — ikisi karışmasın
  diye. z-skor yalnız FRESH kayıtları sayar.
- **Giden mesaj arşivi:** Telegram'a gönderilen her mesaj `data/telegram_outbox.jsonl`'a yazılır
  (denetim için; Telegram export'una gerek kalmaz).

## Proje yapısı

```
config.yaml          tüm eşik/URL/oran (kod içine sabit gömülmez)
holidays_tr.yaml     TR/US tatil takvimi (yılda bir güncelle)
.env                 EVDS + Telegram kimlikleri (git'e girmez)
evds_series.json     keşif çıktısı (teyitli + bulunan kodlar)

AGENTS.md            AI yardımcı ("Usta") kanonik kuralları — araçtan bağımsız
CLAUDE.md · GEMINI.md · .github/copilot-instructions.md
                     IDE köprüleri; hepsi AGENTS.md'ye yönlendirir
ai/                  proje hafızası: PROJECT · STATE · DECISIONS · LESSONS (+ PROFILE, git'e girmez)

src/
  # --- Üretim yolu (GitHub Actions bunları çağırır) ---
  archive_fetch.py   15 dk arşiv çekimi → CSV (kaynak boşsa retry)
  notify.py          eşik değerlendirme + soğuma/tavan → Telegram bildirimi
  daily_job.py       günlük orkestratör: import → EVDS → OHLC → history → rapor → Telegram
  dbdump.py          SQLite ↔ diff'lenebilir metin dump (restore_db.py geri yükler)

  # --- Çekirdek hesap ve veri ---
  util.py            TR sayı ayrıştırma, zaman, config/env, SSL cacert ASCII fix
  calc.py            teorik gram, prim, makas, çeyrek primi, dekompozisyon, z-skor
  db.py              SQLite şema + erişim
  sources/           truncgil.py, yf.py, evds.py
  market_calendar.py forex seansı + tatil + gündüz/gece
  state_machine.py   FRESH/STALE/CLOSED_* + prim geçerliliği
  history.py         tarihsel günlük ons×kur → history_daily (ATR'nin kaynağı; daily_job tazeler)
  ohlc_hist.py       günlük gerçek OHLC (yfinance → ohlc_daily); grafik katmanının verisi
  evds_job.py        EVDS backfill + günlük güncelleme + rapor bağlamı
  import_actions.py  Actions CSV arşivini ana DB'ye aktarır
  reconcile.py       pazartesi hafta sonu mutabakatı

  # --- Karar motoru (Bölüm 8 — ADR #007/#008) ---
  ozellikler.py      TEK özellik giriş noktası (41 özellik); asof=T−1 zorunlu →
                     look-ahead yapısal olarak imkânsız. Canlı ve replay aynı yol.
  gram.py            gram hakemi: "satmak gram kazandırır mı?" + faz-düzeltmeli taban
  karar.py           iki kollu HÜKÜM (çekirdek açık · taktik doğuştan kapalı) + kapı
  tahmin.py          hüküm kaydı (değiştirilemez) → giriş → çözüm → karne
  tahmin_backfill.py aday taraması (karne DEĞİL — örneklem-içi ÜST SINIR)
  grafik_ciz.py      4 panel PNG (matplotlib lazy import; yoksa sessizce atlanır)

  # --- Analiz ve çıktı ---
  indicators.py      kadran/uzlaşı paneli (FRED/yfinance/GLD + etiketleme)
  chart.py           destek/direnç + gösterge teyidi + doğrulama harness'i
  signals.py         sinyal üretimi (gerekçe + güven + geçersizlik)
  backtest.py        rejim / DCA / out-of-sample ölçümleri
  calculators.py     enstrüman karşılaştırma + bilezik başabaş
  trends.py          Google Trends kalabalık göstergesi
  aipaket.py         AI'a yapıştırılacak veri paketi
  report.py          gün sonu markdown raporu
  telegram_bot.py    gönderim + komutlar (long-polling) + giden mesaj arşivi

  # --- Yardımcı / opsiyonel ---
  logging_setup.py   dönen dosya logları
  restore_db.py      data/altin.sql → SQLite (dbdump.restore ince sarmalayıcısı)
  backup_db.py       güvenli SQLite dump (.backup API) — elle çalıştırılır
  evds_discover.py   EVDS kod keşfi
  collector.py · supervisor.py   7/24 yerel toplayıcı modu (config runtime_mode: "collector");
                     üretimde KULLANILMIYOR — Actions modu geçerli

scripts/backup.sh    WAL-güvenli anlık görüntü (yalnız ertelenmiş Oracle senaryosu;
                     git/ağ/silme YOK — bkz. ai/LESSONS.md L-007)
tests/               800+ test — regresyon zırhı (aşağıya bak)
```

### Test paketi — "sözleşme kilidi" (ADR #009)

Testler burada hata avlamaktan çok **sözleşmeyi kilitler**: bu projede yaşanan
en pahalı arızaların hiçbiri birim seviyesinde değildi (bir tablo pipeline'a
bağlı değildi, bir koruma çağrı yolunda geçilmiyordu, bir metrik yapısal olarak
sabitti). Amaç, proje daha zayıf bir model ya da başka bir araçla sürdüğünde
**ihlalin anında kırmızı yanması.**

| Dosya | Neyi kilitler |
|---|---|
| `test_uctan_uca.py` | Zincirin tamamı: izole kökte `daily_job.run()`, ağ kapalı, sentetik veri |
| `test_sozlesme_config.py` | Her `cfg[...]` çözülüyor mu · ölü anahtar · **önceden kayıtlı eşikler gevşetilemez** |
| `test_sozlesme_sema.py` | Şema ↔ dump ↔ Actions stateless döngüsü · değiştirilemezliğin kolon kolon kapsamı |
| `test_sozlesme_workflow.py` | Üretim = 2 YAML: `restore→iş→dump→commit` sırası, `continue-on-error` yokluğu · **CI kapısının varlığı** |
| `test_sozlesme_gizlilik.py` | `.gitignore` iki yönlü doğrulama (L-005) · sır sızıntısı taraması |
| `test_yapisal_korumalar.py` | Tek asof/eşik/maliyet/teorik-gram kaynağı (AST ile) |
| `test_ag_izolasyonu.py` | Karar yolu **soket kapalıyken** çalışmalı; ağ hangi modüllerde olabilir |
| `test_dejenere_metrik.py` | L-010 avı: metrik senaryolara göre değişebiliyor mu · eşik config'ten mi · **rejim tek sınıfa çökmüş mü** |
| `test_veri_butunlugu.py` | `data/altin.sql` denetimi: satır tabanı kilit dişlisi (L-009), hayalet bar yok |
| `test_dokuman_tutarliligi.py` | Devir paketi: köprüler, `ai/` yapısı, L/ADR numara uzayı |
| `test_saf_cekirdek_ozellikleri.py` | Formül değişmezleri (ölçek/kaydırma bağımsızlığı, tek eşik) |
| `test_modul_saglik.py` | Import sağlığı · **imza kilidi** · `__main__` blokları · bağımlılık beyanı |
| `test_bagimsizlik_nobetcisi.py` | L-020 avı: prim'in iki bacağı bağımsız mı — **üretim arşivine karşı iki yönlü** |

**Bir test kırmızıysa önce onun haklı olduğunu varsay.** Çoğu bir ADR'yi ya da
dersi kilitliyor ve gerekçesi docstring'inde yazılı. Testi susturmak, korumayı
sessizce kaldırmakla aynı şeydir (`AGENTS.md` §5 → "Koruma disiplini").

## Yapılandırma

- `config.yaml`: tüm eşikler, URL'ler, seri kodları, oranlar. Kodda sabit yoktur.
- `.env` (`.env.example`'dan kopyala):
  - `EVDS_API_KEY` — https://evds2.tcmb.gov.tr → Profilim → API Key Kopyala
  - `TELEGRAM_BOT_TOKEN` — BotFather
  - `TELEGRAM_CHAT_ID` — @userinfobot

---

## Otonom sistem (üretim)

İki GitHub Actions workflow'u üretimi yürütür; **Telegram'a kendiliğinden mesaj düşer.**
Üçüncüsü (`test.yml`) üretime dokunmaz, yalnız **merge kapısıdır**.

| Workflow | Sıklık | Ne yapar |
|---|---|---|
| `archive.yml` | 15 dk cron | Fiyat çeker → CSV → **bildirim eşiklerini değerlendirir** → tetikte Telegram → commit |
| `daily.yml` | Her gün 15:35 UTC (18:35 TR) | import → EVDS → OHLC → rapor → Telegram → commit (pazartesi mutabakat, pazar haftalık) |
| `test.yml` | Her push + PR | `pytest -q` (872 test). **Üretim işlerine pytest bilerek eklenmedi** — veri toplamayı test altyapısına bağımlı kılar (ADR #014). |

**Secrets (repo Settings → Secrets → Actions):** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`EVDS_API_KEY`.

**Bildirim kuralları (rehber 6.2):** |prim| > %1.5 veya z > 2 · makas > tarihsel p90 ·
günlük hareket > 2×ATR · çeyrek primi z > 2. **Yorgunluk kontrolü:** aynı sinyale 24s soğuma +
günlük tavan (6). Üç bacak FRESH değilse (hafta sonu/tatil) anomali bastırılır; ayrı "pazartesi
beklentisi" mesajı günde 1. Durum `data/alert_state.json`'da.

**Veri kalıcılığı:** SQLite binary repoya girmez; `data/altin.sql` metin dump'ı commit'lenir
(`src/dbdump.py` / `src/restore_db.py`). Böylece repo şişmez ve geçmiş diff'lenebilir kalır.
Actions **stateless** çalışır: DB her koşuda dump'tan kurulur → **bir tablo
`dbdump._TABLES`'ta yoksa her gün sıfırlanır** (`predictions` üçlüsü tam bu
yüzden orada; testle kilitli).

**Tick tekilliği:** `daily_job` her koşumda tüm arşiv CSV'lerini baştan okur.
`ticks(ts_utc, source, symbol)` benzersiz indeksi olmasaydı aynı gözlem her gün
yeniden yazılırdı — ölçüldü: dump'ta 15 999 satırın tekili 1 663'tü (ADR #009-C,
L-013). Dump `INSERT OR IGNORE` yazar ve `restore` indeksi yükleme bittikten
sonra kurar; böylece **eski commit'lerdeki dump'lar da yüklenebilir.**

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
| Kapı açıldığında | Prim z-skor sinyali, çeyrek primi z'si ve `z > 2` bildirimi kendiliğinden devreye girer — kod hazır, ek iş yok |

🔴 **SAYAÇ ŞU AN DURDU (ADR #014).** Bağımsızlık nöbetçisi 2026-08-17 sonrası
günleri `turetilmis` işaretlediği için geçerli gün **30 → 19** düştü ve ileriye
dönük yeni geçerli gün üretilmiyor. Bu bir arıza değil, nöbetçinin doğru
çalışması: sayaç ilerleseydi kapı bir **kimlik** üzerinden açılırdı ve ilk canlı
prim alarmı iki USD beslemesi arasındaki farkı "Kapalıçarşı anomalisi" diye
bildirirdi. Sayaç, bağımsız ons kaynağı devreye girince yeniden ilerler.

⚠️ Kalan 19 günün tamamı **eski yfinance rejiminden** ve o rejim yenisiyle aynı
dağılım değil (F=11.73, ortalama farkı −0.139p). Taban yeni kaynaktan **sıfırdan**
kurulmalı. Ayrıca taban kararı **kanal başına** verilmeli: kuru provada prim
kanalında 0/34, **çeyrek kanalında 6/34 uyuşmazlık** var.

**Kuru prova (dry-run):** Kapı açılmadan `z ne olurdu` her gün ölçülüp
`data/zskor_prova.jsonl`'a yazılır (bildirim gönderilmez). Amaç, eşiğin kapı
açıldığında makul sıklıkta tetiklenip tetiklenmediğini önceden bilmek. Prova iki
tabanı karşılaştırır: **tüm kayıtlar** (mevcut hesap) ve **günlük ortalamalar**
(kapıyla tutarlı taban) — gün içi tekrar örnekleme std'yi bozduğu için ikisi farklı
z üretir.

Haftalık pazar raporundaki "Arşiv İlerlemesi" satırı ilerlemeyi gösterir.

---

## Yerel çalıştırma (geliştirme ve on-demand analiz)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # doldur

.venv/bin/python -m pytest -q                 # 872 test (~10 sn, ağa çıkmaz)
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
.venv/bin/python -m src.chart validate        # grafik_dogrulama.md (faz eşleşmeli taban)
.venv/bin/python -m src.tahmin_backfill       # aday taraması + data/aday_taramasi.json
.venv/bin/python -m src.trends                # Google Trends kalabalık göstergesi
.venv/bin/python -m src.import_actions        # Actions CSV arşivini ana DB'ye aktar
```

**Telegram komutları:** `/hukum` · `/karne [cekirdek]` · `/durum` · `/rapor` · `/net <tutar> <ay> [altın%]` ·
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

## AI yardımcı sistemi (araçtan bağımsız)

Proje bir AI yardımcı sözleşmesiyle gelir: kanonik kurallar **`AGENTS.md`**'de, proje hafızası
**`ai/`** altında (PROJECT · STATE · DECISIONS · LESSONS). Kullanılan IDE ne olursa olsun aynı
davranış üretilir — köprü dosyaları yalnızca AGENTS.md'ye yönlendirir:

| Araç | Okuduğu dosya |
|---|---|
| Codex / Cursor | `AGENTS.md` |
| Claude Code / GLM | `CLAUDE.md` |
| Antigravity | `GEMINI.md` |
| VS Code (Copilot) | `.github/copilot-instructions.md` |

Sohbete `/durum`, `/baslat`, `/karar`, `/plan`, `/kapat` yazmak yeterli (araç özelliği değil,
AGENTS.md'de tanımlı sözleşme). Kararların gerekçesi `ai/DECISIONS.md`'de ADR olarak tutulur.

Devir paketi: **`Proje Yardımcısı - Gold Tracking System/`** — kuralların
taşınabilir ikizi + `ai/PROJE-GUNLUGU.md` (ne inşa edildi, ne ölçüldü, hangi
iddia çürüdü, bugünkü sınırlar). Kural değişikliği **önce köke** yazılır, sonra
oraya kopyalanır; senkron testle denetlenir.

## Kanıt

**`docs/TESLIMAT-ARSIV.md`** — inşa döneminin (Faz 1-7) kanıt kaydı: her fazın ölçümleri,
EVDS teyit tablosu, **geri çekilen iddialar** (rejim üstünlükleri, prim-koşullu DCA,
seviyelerin yön kenarı — hepsi ölçülüp çürütüldü) ve bilinçli olarak yapılmayanların gerekçesi.

Günlük kullanım için `İZLEME.md`. Mimari/araç kararları: `ai/DECISIONS.md` ·
dersler: `ai/LESSONS.md`.
