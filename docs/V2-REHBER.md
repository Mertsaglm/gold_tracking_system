# Birikim V2 — Kullanım ve işletim

## Ne yapar?

BIST ve gram altın iki bağımsız Python projesi olarak çalışır. Her biri kendi
fiyatını okur, kararını üretir ve kendi sanal hesabına yazar. `dashboard/`
içindeki Birikim paneli iki hesabı birlikte gösterir. Bankaya emir gönderen
bir bağlantı, gerçek para veya kredi kullanımı yoktur.

V1 kaynakları ve raporları korunur. Yeni kararın sahibi `advisor/` katmanıdır.
V1 LLM yorumları eski karne ve ayrıntılı araştırma bağlamı olarak kalır;
kanıtlanmamış bir LLM gerekçesi V2'de sayısal fiyat veya işlem miktarı üretemez.

## Bütçe ve karar

`advisor/config.json` içindeki başlangıç varsayımı her hesap için 5.000 TL,
sonraki her ay 5.000 TL katkıdır. “Kredi” borç olarak modellenmez. Kullanıcının
gerçek hisseleri, gramları veya toplam serveti bu hesaplara aktarılmamıştır.
Yeni ay katkısı bir kez yazılır; sistemin koşmadığı aylar nakit olarak tamamlanır.
Kaçırılan tarihlerde geriye dönük alım yapılmaz.

- **AL:** Fiyat, trend, maliyet, net kazanç/risk ve bütçe koşulları birlikte geçti.
- **SAT:** Kayıtlı zarar/hedef sınırı, BIST süre sınırı veya olumsuz görünüm tetiklendi.
- **TUT:** Elde varlık var; satış koşulu oluşmadı.
- **BEKLE:** Güncel veri var, yeterli fırsat yok veya bütçe/risk sınırı dolu.
- **VERİ BEKLENİYOR:** Fiyat/tarih/kurumsal işlem/analiz girdisi doğrulanamadı.

Her işlem; karar kimliği, fiyat kaynağı/zamanı, adet, tutar ve masrafıyla yazılır.
BIST alımları tam lot, altın alımları 0,01 gram adımıyla yapılır. Negatif bakiye,
elde olmayan varlığın satışı ve aynı gün satılanın geri alımı reddedilir.
Altın aylık katkısı yalnız yeni fırsat varsa kullanılır; ay sonu zorunlu satışı yoktur.

## Fiyatın ve sonucun anlamı

- **BIST:** İş Yatırım'ın herkese açık gecikmeli son fiyatı; gerçek emir defteri yok.
  Her yön için 5 baz puan kayma varsayılır. Sayfa önbellek zamanı, hissenin son
  işleminin zamanı değildir; kayıt bu farkı açıkça taşır.
- **Altın:** Döviz.com'un İş Bankası gram ürününün banka alış/satış fiyatı.
  Müşteri alışında banka satış fiyatı, müşteri satışında banka alış fiyatı kullanılır.
  Kaynak yalnız saat yayınladığından gün içi tarihi varsayılır; İşCep kişisel
  kotasyonuyla aynı olduğu ileri sürülmez.
- Altında gün içi GC=F × USD/TRY referansı da aranır. Böylece son analizden sonra
  gerçekleşmiş fiyat değişimi gelecek kazanç olarak ikinci kez sayılmaz.
- Banka makası genişken yeni alış yapılmaz; doğrulanmış fiyatta koruyucu satış
  sadece geniş makas nedeniyle engellenmez. İşlem penceresi hafta içi
  10:15–17:45 İstanbul saatidir. Tatiller ve eski/gelecek zaman damgaları elenir.
- Komisyon, BSMV, KMV, kayma ve varsayılan borsa payı yapılandırmada ve panelde
  açıklanır. Kişisel ekstre tarifesi doğrulanmış değildir.
- Bölünme miktarı/seviyeleri düzeltir. Geç gelen ve geçmiş işlemlerle çelişen
  bölünme, mutabakat isteği olarak görünür. Net temettü **alacaktır**; ödeme tarihi
  kaynağı bulunmadığından nakit olarak harcanmaz. Kanıt referanslı ödeme dosyasıyla nakit mutabakatı yapılabilir; otomatik ödeme kaynağı yoktur.

Portföy değeri, eldeki varlıkların satış masrafı düşülmüş değeri + nakit + bilinen
alacaklardır. Eksik veya bayat fiyat varsa değerleme `null` olur; sıfır zarar gibi gösterilmez.
Yeni katkı kazanç sayılmaz. Al-tut hesabı aynı katkıları, fiyat referansını ve
masrafları kullanır; tam lota yetmeyen payı nakitte bırakır. Mevduat faizi eklenmez.

### Kaynaklar

2026-09-15 tarihinde incelendi:
[İş Bankası komisyon tarifesi](https://www.isbank.com.tr/komisyon-oranlari),
[vadesiz altın hesabı](https://www.isbank.com.tr/vadesiz-altin-hesabi),
[İş Yatırım fiyatları](https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/default.aspx),
[İş Bankası gram referansı](https://altin.doviz.com/isbankasi/gram-altin),
[TBB 2025 bankacılık raporu / KMV düzenlemesi](https://www.tbb.org.tr/sites/default/files/kitaplar/Bankalar%C4%B1m%C4%B1z%202025.pdf).

## Öğrenme nasıl çalışır?

1. Kapanmış geçmişten trend, momentum, oynaklık ve RSI özellikleri çıkarılır.
2. Ridge modeli yalnız sonucu o tarihte tamamlanmış örneklerle eğitilir.
   Test gününün geleceği eğitimde veya ölçeklemede kullanılmaz.
3. Zaman sıralı test blokları ve örtüşmeyen hedef dönemleriyle hata/fark ölçülür.
   Tarihsel banka kotasyonu olmadığı için maliyet 1×, 1,5× ve 2× sınanır.
4. Modelin dahili sınavı tahmin taramasıdır. Ayrı `simulate` komutu tam sanal
   portföy/stop/nakit deneyi sağlar; tarihsel veri sınırları aşağıda açıklanır.
   Sabit güncel evren ve sonradan düzeltilmiş fiyatlar ayrıca yanlılık yaratabilir.
5. Model sınavı ve yeni sanal sonuçlar yeterli olmadan küçük deneme sınırı sürer.
   Kanıtlanmış üstünlük veya kâr garantisi yoktur; panel aksi izlenim vermez.
6. Güncel kararlardan ilk uygulanabilir tahmin mühürlenir. Hedef vadesi dolunca
   düzeltilmiş toplam getiri serisinin değişimi, tahmin hatası ve kaçan yükseliş kaydedilir; bu net banka getirisi değildir. Veri bekleyen
   koşu, değerlendirilmiş yatırım fırsatı gibi sayılmaz.
7. En az 10 bağımsız dönem sonra ölçülen ortalama tahmin yanlılığı, en çok 2
   yüzde puanlık düzeltmeyle yeni tahmine uygulanır. Model yeni fiyatlarla yeniden
   eğitilir; sürümleri ayrı saklanır. Kayıp büyürse risk küçülür; öğrenmenin
   tekrar başlamasını imkânsız yapan kalıcı kilit kurulmaz.

Fed, ECB, TCMB ve BIST KAP arşivi tarihli gündem sağlar. Yaklaşan Fed kararında
yeni deneme tutarı küçültülür. Haber başlıkları sayısal yön skoru veya doğrulanmış
şirket tezi olarak sunulmaz; kaynak hatası “haber yok” sonucuna çevrilmez.

## Komutlar

Komutları ilgili projenin kökünde, kendi Python 3.12 ortamında çalıştır:

```bash
python -m advisor cycle
python -m advisor status
python -m advisor audit
python -m advisor research
python -m pytest -q
```

`cycle` varsayılan olarak mesaj göndermez. `python -m advisor notify` mevcut
`TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` ile son sonucu gönderir. Anahtarlar
yenilenmez veya dosyalara yazılmaz. `--offline` yeni fiyat çekmez; bir deneme
hesabına yönlendirmeden üretim hesabında inceleme amacıyla kullanılmamalıdır.
`--database /mutlak/yol.db` inceleme sırasında ayrı bir SQLite kopyasını salt
okunur açar. Varsayılan veri, repo içindeki SQL dump'tır; GitHub çalışma kopyası
güncel değilse yerel analiz de eski olur. Bayat veri panelde belirtilir.

### Temel dosyalar

| Dosya | İşlev |
|---|---|
| `advisor/config.json` | Bütçe, risk, fiyat ve model kuralları |
| `data/advisor/events.jsonl` | Katkı, fiyat, karar, sanal işlem, sonuç ve bildirim olayları |
| `data/advisor/latest.json` | Panelin okuyacağı son hesap ve analiz görünümü |
| `data/advisor/model.json` | Tekrarlanabilir model önbelleği |
| `data/advisor/models/` | Önceki model sürümleri |
| `data/advisor/run_status.json` | Son koşu tamamlandı mı? |
| `reports/revizyon-denetimi-2026-09-15.json` | Dosya/DB/Telegram envanteri; satır satır semantik denetim iddiası değildir |
| `reports/karar-sonuclari-2026-09-15.json` | Eski kararların sonraki fiyat hareketi |
| `ops/push_retry.sh` | Gönderim başarısızlığını doğru çıkış koduyla bildiren teslim mekanizması |

Defterin eski satırını değiştirme. Hash zinciri bunu reddeder. Açılmış hesabın
başlangıç/bütçe tanımını değiştirmek yeni bir hesap sürümü gerektirir. İlk
kurulumdaki varsayımı değiştirirken eski hesabı silmeden arşivle.

## Otomatik çalışma

`portfolio.yml`, hafta içi 10:17–17:17 TR arasında nominal 30 dakika yedek
zamanlamayla, elle/dışarıdan dispatch ile ve günlük veri workflow'u bitince
çalışır. Dışarıdan gelen 15 dakikalık dispatch'in sahibi doğrulanmadı.
GitHub cron kesin zaman veya kesintisiz fiyat akışı sağlamaz; stop da
yalnız koşunun gördüğü fiyatla simüle edilir. Aradaki fiyat hareketi doldurulmaz.

Altında önce `python -m src.advisor_refresh` önceki tamamlanmış GC=F kapanışını
geçici DB'de doğrular; başarılıysa SQL dump'ını atomik yeniler. Kaynak eksikse
SQL değişmez, yeni sanal alım kapanır. BIST SQL'i yalnız salt okunur.

Sıra: beklenen kapanışı doğrula → fiyat/gündem → karar/defter → GitHub'a kaydet →
Telegram özeti → bildirim makbuzunu kaydet. V2 defterinin tek yazarı bu workflow'dur.
V1 günlük raporu üretmeye devam eder; `ADVISOR_V2=1` ile uzun normal Telegram
raporunun yerini V2 özeti alır. BIST hata uyarıları ve altın arşiv alarm hattı korunur.
Push denemeleri tükenirse koşu kırmızı olur; kurtarma artifact'i 14 gün tutulur.
Telegram ağı başarı cevabını kaybederse sonraki denemede mükerrer mesaj ihtimali
vardır; Telegram API'siyle tam “bir kez teslim” garantisi verilemez.

## Paneli yerelde aç

`dashboard/` Node 22 veya üzeriyle, ek npm paketi kurmadan çalışır:

```bash
node dashboard/server.mjs
```

Adres: `http://127.0.0.1:4173`. Tek proje varsayılan kendi hesabını açar.
İki hesabı birlikte göstermek için sunucuya `BIST_SNAPSHOT` ve `GOLD_SNAPSHOT`
ortam değişkenleriyle iki `latest.json` dosyasının mutlak yollarını ver.

Panel; arama/karar filtresi, eldeki varlıklar, işlem defteri, JSON dışa aktarımı,
aynı bütçeli al-tut, öğrenme karnesi ve eski sonuçları içerir. İlk iki gün
birikmeden çizgi grafik uydurulmaz. Parola gerekiyorsa `ADVISOR_DASHBOARD_PASSWORD`
ayarlanabilir; tarayıcı parolayı yalnız oturum belleğinde tutar.

## Canlı panel ve Vercel

Canlı adres: [birikim-paneli.vercel.app](https://birikim-paneli.vercel.app/).
Paneli izlemek için Mac'te Node sunucusunu açık tutmak gerekmez. Portföy çevrimleri
GitHub Actions'ta çalışır; Vercel yalnız iki depodaki son `latest.json` görünümünü sunar.
Yerel `node dashboard/server.mjs` komutu geliştirme ve çevrimdışı inceleme içindir.

Kurulum ve yeniden yayın denetimi:

1. Vercel proje root directory'si `dashboard`; framework `Other`/otomatik yok.
   Yapılandırma `dashboard/vercel.json` içindedir. Zamanlama GitHub'da kalır.
2. Sunucuda `ADVISOR_GITHUB_TOKEN`: özel `Mertsaglm/bist-analiz` deposu için
   yalnız Contents Read yetkili fine-grained token. `Mertsaglm/gold_tracking_system`
   herkese açık olduğu için aynı tokenın o depoya ayrıca erişmesi gerekmez.
   Token tarayıcıya gönderilmez ve repoya yazılmaz.
3. `ADVISOR_DASHBOARD_PASSWORD`: panel giriş parolası. Ayarsız sunucu özel hesap
   verisini yayınlamaz, 503 döner. Kullanıcı adı sabit `mert`.
4. Production'da iki hesabı ve veri tarihlerini kontrol et. Parolasız
   `/api/status` isteği 401 dönmelidir; yeni arşiv gelince paneldeki tarih yenilenmelidir.
5. Production adresi iki `advisor/config.json` içindeki `dashboard_url` alanında
   tutulur. Telegram özeti panel bağlantısını ekler.

Vercel endpoint'i salt okunurdur. Dosyayı her istekte yeniden analiz etmez;
GitHub'daki son görünümü okur. İstek yeni model eğitimi veya al/sat tetiklemez.
API anahtarlarını, Telegram tokenını veya GitHub tokenını public/client dosyalara
koyma. Mevcut servis anahtarları bu revizyonda değiştirilmedi.

## Doğrulama

`tests/test_advisor_v2.py` ve `tests/test_advisor_flow.py`; para korunumu,
tekrar koşu, zaman sızıntısı, eksik fiyat, bölünme, tahmin çözümü, koruyucu satış
ve arşiv teslimini sınar. İkinci dosya geçici hesapta alış → tekrar → yeniden
açılış → satış zincirini çalıştırır. Dış kaynaklar fixture'dır; gerçek işlemler yoktur.

```bash
cd dashboard
npm test
npm run build
```

Node testleri özel veri erişimini, yalnız okuma API'sini ve bir hesabın bozuk
olduğunda diğer hesabın görünmeye devam etmesini sınar. Test sayıları yerine
bu komutların güncel sonucu esas alınır.

## Getiri eğrisi

Her iki hesabın ve al-tut karşılaştırmasının getirisi, eklenen paradan arındırılarak deftere yazılır. Panel son 500 günün son değerlemesini gösterir; saatlik kayıtların tamamı olay defterinde kalır. İlk günün alım/satım maliyeti sonuçtan düşer.

## 2026-09-16 geliştirmeleri ve yeni komutlar

Öncelik ve kapsam: [25 maddelik plan](IYILESTIRME-2026-09-16.md).
Sonuçlar: [uygulama raporu](../reports/IYILESTIRME-2026-09-16.md).

- Önceki işlem gününün kapanışı eksikse yeni alım durur; güncel, geçerli fiyatla mevcut stop/hedef izlenir.
  Eski fiyat güncel portföy değerine ve yeni işlem bütçesine girmez.
- Takvim YAML olarak okunur. Yarım gün 12:15 kapanışı sistemin ihtiyatlı işlem
  penceresidir; resmî piyasa kapanışı iddiası değildir. Vade seans sayısıyla ilerler.
- Toplam stop riski `max_portfolio_risk_pct` ile sınırlanır. Eksik değerlemede
  risk artırılmaz. Ortak düşüş senaryoları stop dolum garantisi vermez.
- Al-tut hesabında varlık başına kalan nakit sonraki katkıyla birleşir;
  bir eksik kotasyon diğer varlıkların alımını durdurmaz.
- Yeni riskin büyümesi en az 24 örtüşmeyen dönem, pozitif güven alt sınırı ve
  mevcut kapalı işlem şartına bağlıdır. Önceki sabit model ve günlük model
  ayrıca eşit başlangıç bütçeli iki gölge hesapta izlenir; otomatik model terfisi yoktur.
- Karar detayları miktar, tutar, masraf, hedef/stop sonucu ve önceki kararla
  değişimi gösterir. Bekleme nedenleri ile haftalık katkı ve yatırım sonucu ayrıdır.

Python 3.12 ortamını `requirements-runtime.txt` ile kur. BIST'te ayrıca
`pip install --no-deps -e .` kullan. Kaynak bağımlılık aralıkları pyproject.toml
(BIST) / requirements.txt (altın) içinde kalır; sürüm değişince kilidi ve iki
suite'i birlikte doğrula. Altın kilidi pandas 2.3.3 kullanır.

İlgili projenin kökünde:

```bash
python -m advisor watchdog
python -m advisor weekly
python -m advisor backup --output /tmp/advisor-yedek.zip
python -m advisor recovery-check --input /tmp/advisor-yedek.zip
python -m advisor simulate --start 2026-06-01 --end 2026-08-26 --output /tmp/portfoy-deneyi.json
python -m advisor reproduce --input /mutlak/yol/karar-kapsulu.json.gz
python scripts/advisor_manifest.py
```

`watchdog` gözlemdir, hesabı onarmaz veya durdurmaz. Ayrı Actions işi kaçırılan
seans kontrolünü, 45 dakikayı aşan gerçek çevrim boşluğunu, hata/eksik fiyatı
ve teslim makbuzunu inceler; sorun exit 1'dir.
`advisor-recovery.yml` ayrı yedeği geçici dizinde doğrular; artifact 90 gün tutulur.
Arşiv hesap verisi içerir; paylaşım için hazırlanmış bir dosya değildir.
`recovery-check` mevcut verinin üstüne yazmaz. Yedek adı daha önce varsa reddedilir.

Her yeni karar koşusu girdi, ayar, model, defter başlangıcı, kullanılan Python kodu
ve bağımlılık sürümlerini `data/advisor/capsules/` altında mühürler. `reproduce`
arşivlenmiş kodu geçici dizinde çalıştırır; güvenilir kendi karar paketlerinde
kullanılır. Bağımlılık ortamı farklıysa aynı sonucu üretmiş sayılmaz.

Tam portföy `simulate` komutu, zaman sıralı eğitim ve ortak karar/muhasebe motorunu
kullanır. Günlük bar içinde stop ve hedef görülürse stop önce varsayılır; açılış
boşluğu stop fiyatından doldurulmaz. Haber gündemi, tarihsel banka kotasyonu ve
ayrı tarihli tüm kurumsal nakit/lot akışları tam olarak yeniden kurulmaz.
Bu yüzden rapor `production_eligible: false` taşır; geçmiş sonucu canlı kanıt
kapısına aktarmaz. Stres dosyası örneği:

```json
{"cost_multiplier":2,"skip_every":3,"gap_day":"2026-07-01","gap_down_pct":10,
 "untradable_symbols":["AAA"],"untradable_days":["2026-07-02"],"stale_days":["2026-07-03"]}
```

Bu JSON'u `--scenario /mutlak/yol/stres.json` ile simülasyona ver. AAA test
sembolüdür; inceleme evrenindeki sembolle değiştir. Her üç kontrolden birini
atlama, iki kat maliyet, fiyat boşluğu, satılamama ve bayat kotasyon ayrı varsayımlardır.

### Kanıtlı veri içe alma

Aşağıdaki komutlar kayıt yazar; yalnız doğrulanmış belgelerle kullanılır.
Bu geliştirmede gerçek ödeme veya kişisel masraf gözlemi içe alınmadı.

- `python -m advisor universe-import --input /mutlak/yol/uyelik.json`:
  JSON liste satırında `symbol`, `known_at`, `effective_from`, `active` (boolean),
  `source`; isteğe bağlı `effective_to`. Gelecekte öğrenilen üyelik geçmişe taşınmaz.
  Kayıt `advisor/universe-history.json` olur. Kaynak yoksa güncel evren varsayımı
  raporda açıkça belirtilir; eski üyelik uydurulmaz.
- `python -m advisor settle-dividends --input /mutlak/yol/odeme.json`:
  JSON liste satırında defterdeki `receivable_key`, kuruş cinsinden tam eşleşen
  `amount_cents`, `paid_on` (YYYY-MM-DD), `source_reference`.
  Alacak bir kez nakde döner; toplam servet artmaz. Her sanal hesabın alacağı
  kendi anahtarıyla mutabık olmalıdır. Doğrulanmış ödeme akışı otomatik kurulmuş değildir.
- `python -m advisor cost-observations --input /mutlak/yol/masraf.json`:
  JSON liste satırında `symbol`, `side` (BUY/SELL), `reference_price`,
  `observed_price`, `expected_fee_try`, `observed_fee_try`, `source_reference`.
  Fiyat/masraf farkı kaydedilir; gerçek veya sanal emir oluşturmaz.

`weekly` yalnız özet basar. `weekly --notify` mevcut Telegram hattından cuma
18:00 sonrasında haftada bir gönderir. Otomatik çağrı mevcut tek yazarlı
`portfolio.yml` içindedir. Gerçek teslim, yayın sonrası doğrulanmalıdır.

### Ortak kod bakımı

İki projedeki `advisor/*.py` dosyaları aynı manifestle doğrulanır. Her projede
`python scripts/advisor_manifest.py` CI sözleşmesine dahildir. BIST kökünde
`python scripts/advisor_manifest.py --peer ../gold_tracking_system` iki gerçek
kopyayı da karşılaştırır. `--write --peer ...` yalnız iki kopya eşitse manifesti
bilinçli günceller. Projeye özgü kurallar `advisor/config.json` içinde kalır.
