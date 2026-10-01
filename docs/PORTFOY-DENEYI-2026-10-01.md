# Çekirdek/taktik sanal sınavı — 2026-10-01

Bu paket ana BIST/altın hesaplarının kararını değiştirmez. Ayrı defterlerde aynı
başlangıç ve katkılarla beş kol açar: mevcut politika, %80 çekirdek + %20 nakit,
çekirdek + pasif kalan dilim, çekirdek + mevcut Ridge ve çekirdek + piyasaya özel
Ridge. `advisor/config.json` içindeki `experiment_start_date` iki repoda da
`null` olduğu için **ileri T0 başlamamıştır**. BIST ile altın arasında para aktarılmaz.

## Uygulanan sözleşme

- Her yeni kol 50.000 TL başlangıç ve aylık 5.000 TL alır. Çekirdek/taktik
  hesaplar 80/20 ayrı defter bölümleridir; tek BIST saklama ücreti ikiye katlanmaz.
- BIST çekirdeği o gün bilinen 30 üyeyi eşit ağırlık hedefiyle alır; CCOLA/CIMSA
  yalnız taktik havuzundadır. 2026-10-01 DSTKF çıkışı/TRMET girişi tarihli
  üyelikten okunur. Endeks çıkışı ilk uygun sanal kotasyonda izlenir.
- Altın çekirdeği İş Bankası GRAM kotasyonunda düzenli alım yapar. Çekirdek
  model onayı, RSI veya tahmini R:R beklemez; kalite, kotasyon ve bütçe ister.
- Taktik BIST haftalık sıralama, ilk beş giriş/ilk on koruma, isim başına %4
  değer ve %0,2 stop zararı, toplam %20 taktik değer ve beş pozisyon sınırı
  uygular. Aynı sektörden ikiden çok yeni isim açılmaz. Altın taktik bütçesi
  %20, stop zararı %1 ile sınırlıdır. Masraf sonrası giriş eşiği %1'dir.
- Stop ve üyelik çıkışı haftalık yeniden seçim dışında da izlenir. Geçerli
  kotasyon, sonraki fiyat ve aynı kotasyonun tek dolumu zorlanır. Stop fiyat
  boşluğu gerçek gözlenen kotasyondan yürür; geçmiş sentetik gram serisinden
  gün içi dolum türetilmez. Çekirdek piyasa riski stop riskinden ayrı açıklanır.
- Karar izi sayısal kapıları, ham/kalibre tahmini, model/özellik kimliğini,
  hedef portföyü ve son belirleyici kodu saklar. KAP/makro haberinin yayın ve
  **ilk yerel görülme** zamanı ayrı tutulur; ilk görülme eski tarihe yazılmaz.

## Tekrar üretilebilir kontroller

```bash
.venv/bin/python -m pytest -q
npm test --prefix dashboard
npm run build --prefix dashboard
.venv/bin/python scripts/advisor_manifest.py --peer '../BIST tahmin'
.venv/bin/python scripts/portfolio_preflight.py
.venv/bin/python scripts/portfolio_smoke.py
.venv/bin/python scripts/portfolio_research.py --market gold
```

Model sınavı yalnız offline'dır; BIST'te LightGBM için diğer repodaki
`requirements-research.txt` gerekir.
LightGBM canlı sanal adayın işlem kararına bağlanmaz. Araştırma raporu her sabit
adayı, başarısız bölmeyi, etiket/test tarihlerini ve deneme sınırını saklar.
Üretim SQL kopyasıyla yeniden prova için `portfolio_smoke.py` komutuna
`--archive` ile indirilen dosya, `--output` ile ayrı makbuz yolu verilir;
komut kaynak arşive veya üretim defterine yazmaz. Makbuzdaki
`source_archive_sha256`, aşağıdaki indirme hash'iyle eşleşmelidir.

Tarihli makbuzlar:

- BIST: diğer repoda `../BIST tahmin/reports/portfolio-smoke-bist-2026-09-24.json`,
  `../BIST tahmin/reports/portfolio-model-research-bist-2026-09-24.json`.
- Altın: bu repoda `reports/portfolio-smoke-gold-2026-09-22.json`,
  `reports/portfolio-model-research-gold-2026-09-22.json`.

BIST yerel SQL'nin son kapanışı 2026-09-24'tür. O günde DSTKF ve TRALT barı
bulunmadığı için tarihli kopya provasındaki çekirdek 30 yerine 28 hissede
alım yapmıştır. Altın yerel SQL 2026-09-22'de biter. Test kotasyonları
`historical_assumption` olarak işaretlidir; canlı banka/emir dolumu değildir.
İki arşiv kopyasında beş kol, tekrar finansal olay değişmezliği, altışar
defterin bağımsız nakit/lot mutabakatı ve yedek geri okuması geçti. Taktik
işlem tutarında yarım kuruşu `float` ile çarpmak bir kuruşluk fark
oluşturuyordu; `Decimal` hesap ve regresyon testiyle düzeltildi. Eksik BIST30
üyeliği alımı durdurur; engellenmiş taktik satış haftalık kontrolü tamamlanmış
sayılmaz. Bu, **ortak ileri T0 için taze veri hazır** demek değildir.
2026-10-01'de indirilen üretim SQL'leriyle, orijinal dosyalara yazmadan aynı
prova tekrarlandı. [BIST makbuzu](../../BIST%20tahmin/reports/portfolio-smoke-bist-production-copy-2026-09-30.json)
2026-09-30 kapanışından sonraki varsayımsal 2026-10-01 çevriminde 32 geçerli
kotasyon, 30 çekirdek pozisyon, beş aday ve altı mutabık defter gösterir.
[Altın makbuzu](../reports/portfolio-smoke-gold-production-copy-2026-09-30.json)
aynı günün tarihli gram kapanışıyla beş aday/altı defter gösterir. İki makbuzda
tekrar işlem ve yedek farkı yoktur; fiyatlar **tarihsel varsayımdır**, canlı
işlem veya ileri performans kanıtı değildir. İlk BIST provası, karşılaştırma
sepetindeki yarım kuruş `float` hatasını yakaladı; `Decimal` düzeltmesi ve
regresyon kilidi sonrası geçti.
2026-10-01 hazır olma kontrolü `ready: false` verdi: bugünkü BIST30 kümesinde
son yerel kaynak gününün TRALT ve TRMET barı eksik, her iki arşiv de beklenen
2026-09-30 kapanışının gerisinde. T0 geçmişe veya tatil gününe konamaz.
Çıkış kodu 2 bilinçli hazır-değil sonucudur. Kontrolün `ready` alanı yalnız
**yerel arşiv/T0** içindir; `production_ready` dış kanıt gelene kadar false'dur.

2026-10-01 salt-okunur [uzak altın durumunda](https://github.com/Mertsaglm/gold_tracking_system/blob/a3437274415c1218c1bca12b301ea88704dd8e5e/data/advisor/latest.json)
14:33 UTC kapsülü 2026-09-30 analizini, 10.000 TL katkıyı, sıfır ana işlem ve
pozisyonu gösterdi. [Uzak altın ayarı](https://github.com/Mertsaglm/gold_tracking_system/blob/a3437274415c1218c1bca12b301ea88704dd8e5e/advisor/config.json)
eski 5.000 TL başlangıçlı sürümdedir; yeni beş kol orada yoktur. GitHub'da
07:02–14:46 UTC arasında 33 `advisor: sanal portfoy` commit'i gözlendi;
en büyük ardışık boşluk 15,3 dakikaydı. Bu gerçekleşen **altın çıktı ritmini**
gösterir; dış tetikleyicinin kimliğini kanıtlamaz. Özel BIST deposu bağlı API'de
404 döndü, fakat mevcut Safari oturumunda salt-okunur açıldı. 2026-10-01
[BIST üretim ayarı](https://github.com/Mertsaglm/bist-analiz/blob/2e64feaf12917757f04ff1f8261c8509277cae7b/advisor/config.json)
50.000 TL başlangıçlı eski ana hesabı taşır; yeni T0/aday modülü yoktur.
[BIST snapshot'ı](https://github.com/Mertsaglm/bist-analiz/blob/2e64feaf12917757f04ff1f8261c8509277cae7b/data/advisor/latest.json)
2026-09-30 analiz tarihini taşır. [Çalışma makbuzu](https://github.com/Mertsaglm/bist-analiz/blob/2e64feaf12917757f04ff1f8261c8509277cae7b/data/advisor/accounts/paper-2026-09-25/run_status.json)
14:46:54 UTC'de `ok=true, skipped=false` der. Görünen 29 BIST portföy commit'i
08:02–14:47 UTC arasında; en büyük ardışık boşluk 17 dakikadır. Bu çıktı
ritmidir, tetikleyicinin kimliği değildir. GitHub CLI kimliği geçersiz kaldı;
güncel iki üretim olay defteri Safari üzerinden salt-okunur kopyalandı.

Sabitlenmiş üretim commit'lerinden iki SQL dökümü Safari ile salt-okunur
indirildi ve yalnız geçici SQLite dosyalarına geri yüklendi:
[BIST SQL](https://github.com/Mertsaglm/bist-analiz/blob/2e64feaf12917757f04ff1f8261c8509277cae7b/data/bist.sql)
SHA-256 `dbe20b128d146580227d989444e179165425f9d8962e896090b4f455b90c0a06`;
73 hissenin 2026-09-30 barı, bu tarihteki 30 BIST30 çekirdek üyesinin de
barı ve beş endeks/kur serisinin 2026-09-30 kaydı mevcut. Yerel BIST SQL
SHA-256 `040bf4603ca2e8351db30f1b3af748b413e65d41726e635ce37564f4e323ff03`.
[Altın SQL](https://github.com/Mertsaglm/gold_tracking_system/blob/a3437274415c1218c1bca12b301ea88704dd8e5e/data/altin.sql)
SHA-256 `61bdc0936a202d6d6db14e47b02d8c4a7205f1835d7815e6bd4593990fa1e480`;
`history_daily` 2026-09-30'a ve GRAM banka tick'i 2026-09-30 20:14 UTC'ye
uzanır; `GC=F`/`TRY=X` OHLC ise 2026-09-29'da biter. Yerel altın SQL
SHA-256 `7e8bc0c8e945b9acf128154bd6c238759c403a8e48324dbfa4da92f3f1a05467`.
Bunlar canlı kopyaların yerelden daha güncel olduğunu doğrular; 2026-10-01
kapanışının tamamlandığını göstermez. [BIST güncel ana hesap
defteri](https://github.com/Mertsaglm/bist-analiz/blob/2e64feaf12917757f04ff1f8261c8509277cae7b/data/advisor/accounts/paper-2026-09-25/events.jsonl)
SHA-256 `9a92a702fa5871d76dee064f02b79818d6daf47d8148d09c80ce3fd38ce67f39`:
7.124 olayın hash zinciri doğrulandı; son olay 2026-10-01 14:46:54 UTC.
Bağımsız muhasebe dört hesapta `Ledger.account` ile eşleşti: ana strateji
55.000 TL nakit ve sıfır pozisyon/işlem; 60 dolum yalnız karşılaştırma
hesabındadır. Kök `data/advisor/events.jsonl` ayrı, eski defterdir; [son
değişim commit'inin](https://github.com/Mertsaglm/bist-analiz/commit/9f4182ffcfca55f0401dde19e2f06c31af430316)
yerel kopyayla eşliği güncel ana hesap için kanıt sayılmaz.
[Altın üretim defteri](https://github.com/Mertsaglm/gold_tracking_system/blob/a3437274415c1218c1bca12b301ea88704dd8e5e/data/advisor/events.jsonl)
SHA-256 `44381f24af599d0c4668dcc5f94bd62ea582ec3befa999770c0aeaaae8805e0c`;
Git blob `ef910da854838ec879f9ddc4804f7eb965972847` ve 1.863 olayın
hash zinciri doğrulandı. Dört hesabın bağımsız muhasebesi eşleşti: ana
strateji 10.000 TL nakit, sıfır pozisyon/işlem. Bunlar üretim defteri
bütünlüğünü gösterir; yeni kodun üretimde çalıştığını göstermez.
Eski **yerel** defterlerde 148 BIST ve 86 altın karar kapsülü, kayıtlı kaynak
kodu ve sabit bağımlılık sürümleriyle yeniden üretildi. Bu kontrol güncel
üretim kapsüllerini kapsamaz. Altın yerel sanal ortamı bu doğrulama sırasında
`pandas==2.3.3` ve `tzdata==2026.3` çalışma zamanı kilidine eşitlendi.

GitHub Actions [BIST manuel tetikleme](https://github.com/Mertsaglm/bist-analiz/actions/runs/36878914856)
ve [planlı yedek koşu](https://github.com/Mertsaglm/bist-analiz/actions/runs/36876377339),
ayrıca [altın manuel tetikleme](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/36878914565)
ve [planlı yedek koşu](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/36877224855)
kayıtlarını gösterir. `workflow_dispatch` kayıtları yaklaşık 15 dakikalık
çıktı ritmiyle uyumludur; dış dispatch hizmetinin kimliğini doğrulamaz.

Offline son 126 test gününde seçilmiş BIST evreni için göreli Ridge Rank IC
ortalaması 0,0084, LightGBM 0,0022'dir; MAE sırasıyla 7,659 ve 7,713
yüzde puandır. Altında temel ve ons/kur Ridge MAE'si 11,619 ve 11,747
yüzde puandır. Bu arşiv sonuçları üstünlük göstermiyor. BIST evreni sonradan
seçilmiştir; arşivin son günü 2026-09-24, üyelik kaydı 2026-09-25'tir.
Hesaplanabilir maliyetli, bağımsız portföy getiri serisi olmadığından DSR
hesaplanmadı. Hiçbir model otomatik terfi etmez.

## T0 ve yayın sınırı

Önce 2026-09-30 yerel üretim düzeltmelerinin güncel üretim sürümüyle farkı,
iki piyasada taze kapanış/fiyat, aktif ve eski defter hash'i, kurumsal işlem,
iş sırası ve dış scheduler gerçekleşmesi doğrulanmalı. Kopya provasının
geçmesi canlı üretim eşliği kanıtı değildir. Ortak sonraki işlem günü T0
seçilip iki config'de aynı tarih girildiğinde yeni kollar açılır; geçmiş
hesaplar yeniden ölçeklenmez. 20 seans çalışma, 63/126 seans ekonomik
değerlendirme için ayrı eşiklerdir; erken işlem sayısı üstünlük sayılmaz.

Bu deney `codex/portfolio-research` dalında hazırlanır. Üretim yayını ve
BIMAS geçmiş karne düzeltmesi ayrı onay gerektirir. Geri dönüş yeni adayın yeni işlemlerini durdurur;
eski sanal defter silinmez.
