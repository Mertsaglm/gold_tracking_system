# PROJECT.md — Projenin Kimliği

Güncel devir ve açık işler [STATE](STATE.md), son denetim kanıtı [24 Kasım raporunda](../docs/DENETIM-2026-11-24.md).

## Araştırma yaklaşımı — 2026-11-24

Mevcut ana strateji ve eş bütçeli pasif kol referanstır. Kontrollü rakipler
ayrı sanal hesaplarda veya zaman sıralı replay'de fiilen sınanır. Veri
güvenilirliği ve muhasebe kuralları ortak kalır. Trend, makas, R:R ve
tahsis ekonomik hipotezlerdir. Katkıdan arındırılmış net getiri, düşüş,
maliyet, kapsama ve reddedilen fırsatlar ön kayıtla izlenir. İlk deneme
üstünlük kanıtı gerektirmez. Ana politika için ileri ekonomik kanıt gerekir.
Ortak T0 yalnız ortak beş kolun başlangıcıdır. Bağımsız araştırmalar sürer.

## Revizyon hedefi — 2026-11-19

BIST ve İş Bankası gram altını için iki ayrı otomatik sanal hesap. Her piyasa
50.000 TL ile başlar ve ayda 5.000 TL katkı alır. Hedef, banka maliyetlerinden
sonra serveti uygun AL/SAT kararlarıyla artırmak. Pasif kol aynı parayla
otomatik işler. Yeni modeller ayrı defterde otomatik ölçülür. Açık pozisyon
yeni fiyat, risk veya sinyal değişince yeniden değerlendirilir. Tahminin
ölçüm ufku, zorunlu pozisyon süresi olarak kullanılmaz. Yaklaşık saatlik
bulut gözlemi ve kısa gün sonu Telegram raporu, bilgisayar kapalıyken de
çalışmalıdır. Gerçek emir, elle rutin tetikleme ve ek harcama kapsam dışıdır.

## İşletim bütçesi — 2026-10-29

Mert ek ödeme yapamayacağını belirtti. Ücretli servis/LLM açılmaz, harcama limiti
artırılmaz ve özel depo herkese açılmaz. Eski düşük maliyet/LLM bütçe kararlarının
yerine geçer. BIST günlük otomasyonu V1 LLM olmadan veri/rapor üretir;
deterministik V2 çalışmaya devam eder. Saatlik gözlem stop kontrol sıklığını da
azaltır; gerçek zaman garantisi yok. Yerel hazırlık ve üretim kabulü ayrı tutulur.

## İleri sanal sınav kapsamı — 2026-10-01

Ana/önceki altın hesapları korunur. BIST ile ortak ileri T0 sonrasında ayrı
50.000 TL + aylık 5.000 TL sanal bütçeyle beş kol izlenir. %80 GRAM çekirdeği
geçerli İş Bankası kotasyonunda düzenli birikimdir; en fazla %20 taktik
masraf sonrası tahmin ve stop riskiyle sınırlanır. Taktik kârı çekirdek + nakit
ve çekirdek + pasif altın kollarına göre ölçülür. Ons/kur Ridge yalnız ayrı
model adayıdır; üstünlük veya otomatik terfi kabul edilmez. Gerçek emir yok;
ortak T0 henüz açılmadı. Ayrıntı: `docs/PORTFOY-DENEYI-2026-10-01.md`.
Kod 2026-10-01'de iki deponun `main` dalına yayımlandı. Altın ilk yeni kod
çevrimi/Telegram makbuzu geçti; BIST ilk yeni koşusu seans dışında atlandı.
Beş deney hesabının canlı çalışması, ortak gelecek T0 ön koşullarına bağlıdır.

## Karar ölçümü — 2026-11-24

60 takvim günü yeni strateji alımı yoksa işlemsizlik incelemesi yapılır.
BEKLE ölçümü kapıları, masraf sonrası varsayımsal getiriyi, eşleşen pasif
kıyası ve eksik vade kotasyonunu gösterir. Zorunlu tahsis yalnız ayrı,
ön kayıtlı bir deney olarak değerlendirilebilir. Ortak T0 açılışı uygun
kotasyona, eş bütçeye ve iki piyasanın canlı kabulüne bağlıdır.

## Güncel kapsam — 2026-09-25

Mert'in yeni talebi: BIST ve İş Bankası gram altını için iki ayrı otomatik analiz ve
sanal portföy, ortak web paneli, kısa ve net Türkçe Telegram kararları. Amaç masrafları
hesaba katarak birikimin değerini, hisse/gram miktarlarını artıracak fırsatları izlemek.
Gerçek emir iletimi yok. Bütçe her hesapta 50.000 TL başlangıç + aylık 5.000 TL; faizsiz nakit.
Yeni bütçe ayrı hesap kimliğindedir. Sınırlı aday kataloğu ayrı defterlerde sınanır;
hiçbir adayın üstünlüğü peşinen kabul edilmez. Ayrıntı: `docs/REVIZYON-2026-09-25.md`.
Kullanıcının gerçek varlıkları bilinmediğinden yeni sanal hesaplara aktarılmadı.

`advisor/` güncel karar/defter hattıdır; `src/` eski veri toplama ve araştırma hattıdır.
Mevcut API anahtarları korunur. Sayısal karar bankaya özgü referans fiyat, masraf, trend,
risk ve zaman sıralı ölçüme dayanır. Kesin ifade eylemi belirtir; fiyat tahminine kesinlik
atfetmez. Yeni sonuçlar olgunlaşınca sınırlı hata düzeltmesi uygulanır.

Başarı tanımı: para korunumu ve tekrar çalıştırma testleri geçer; fiyat eksikliği görünür;
her işlem fiyatı ve masrafıyla izlenir; katkılar hariç getiri aynı bütçeli al-tut ile
karşılaştırılır. Ayrıntı: `docs/V2-REHBER.md` ve `reports/REVIZYON-2026-09-15.md`.

## Mimari ve teknik sınırlar

- Python 3.12; yerelde macOS, üretimde GitHub Actions. SQLite'ın deterministik
  `data/altin.sql` arşivi ile V2 olay defteri ayrı kayıtlardır. Eski yerel SQLite'tan
  dump üretmek üretim arşivini geriye sarabilir (L-009).
- Ortak `advisor/` motoru BIST deposuyla `advisor/shared-manifest.json` ve
  `scripts/advisor_manifest.py` üzerinden eşlik kontrolü taşır. Ortak panel BIST
  deposunun `dashboard/` klasöründedir; iki hesabı okur, karar/işlem yazmaz.
- Açılmış hesabın bütçesi ve geçmişi geriye dönük değiştirilmez; yeni bütçe/yöntem
  ayrı hesap veya deney kimliği alır. Katkı kâr değildir. Eksik/bayat fiyat,
  kesin servet veya sıfır zarar sayılmaz.
- Önceki tamamlanmış kapanış olmadan yeni alım yok; geçerli güncel kotasyonla
  mevcut koruyucu çıkış ayrı değerlendirilir. Kotasyonun okunma saati yeni fiyat
  değildir. Banka referansı gerçek dolum veya kesintisiz stop gözetimi değildir.
- Model eğitimi/kalibrasyon zaman sıralıdır; sonuçlanmamış etiket eğitime girmez.
  Mühürlü tahmin vadesi ayar değişikliğiyle değişmez. Replay ve düşük tahmin hatası
  canlı getiri üstünlüğü değildir; başarısız sınav sonrası eşik gevşetilmez.
- `collector.py`, `supervisor.py` ve `deploy/` alternatif işletim altyapısıdır;
  üretimde kullanılmıyor diye silinmez (L-006). GitHub cron'u zaman garantisi vermez.

## V1 araştırma sınırları ve geçmiş

V1'in amaç fonksiyonu terminal gram sayısıdır, TL getirisi değil. Bu eski
karne/kapı ölçütü V2'nin maliyet sonrası servet ve pasif kol kıyasına taşınmaz.
Tam kayıt: `ai/archive/PROJECT-V1-2026-10-02.md`.

Prim'in iki fiyat bacağı bağımsız olmalıdır; aynı satıcıdan türetilmiş günler
z-skor kapısına sayılmaz (ADR #014). Canlı spot ons ile tarihsel GC=F ayrıdır;
vadeli kontrat roll'ü prim sinyali değildir. Ons ve kurun farklı anlara ait
high/low değerlerinden gram OHLC uydurulmaz; nominal `^TNX` reel faiz yedeği değildir.

Eski Telegram komutları `/hukum`, `/karne`, `/durum`, `/rapor`, `/net`, `/bilezik`,
`/grafik`, `/aipaket` yalnız yerelde `python -m src.telegram_bot` açıkken yanıt
verir. Actions üretimi push-only'dir; gelen komutu okumaz (ADR #012-E).
İnşa dönemi Faz 1–7 kaydı `PROJE-REHBERI.md`'dedir; güncel V2 için
`docs/V2-REHBER.md` ve `ai/DECISIONS.md` esas alınır.
