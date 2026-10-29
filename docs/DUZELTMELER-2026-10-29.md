# Yerel ücretsiz işletim düzeltmeleri — 2026-10-29

Bu dosya yayın öncesi doğrulama kesitidir. Mert 2026-10-29 tarihinde
commit/push ve gerekli güvenli işlemleri yetkilendirdi. Canlı kabul ayrı doğrulanır. Ek ücretli servis,
limit artışı veya gerçek emir yok. Üretim SQL/defter/geçmiş kapsüller ve deney T0 korundu.

- Geçerli geniş makas ayrı `BEKLE/spread_limit` sonucu verir; %3 alım eşiği ve
  mevcut pozisyon stop çıkışı korunur. Gerçek kaynak/tazelik hatası alarm kalır.
- HTTP hatası güvenli aşama/status ile tanılanır; geçici timeout/bağlantı/429/5xx
  en fazla üç GET ile denenir. Kalıcı 4xx ve parser hatası tekrar edilmez;
  URL parametreleri, sayfa gövdesi ve anahtarlar tanıya yazılmaz.
- Yeni kapsüller defter öneklerini ve kodu mühürlü ortak nesnelerle saklar.
  Eski bağımsız v1 kapsüller aynı sonucu üretmeye devam eder; kanıt silinmez.
  V2 kapsül taşınırken ledger/sources alt dizinleri birlikte korunur.
- Operasyon yedeği Pazartesi/Çarşamba/Cuma, artifact saklama 3 gün.
  Hata kurtarma artifact'i de 3 gündür; bütün defter/model dosyalarını korur,
  kapsülleri dışarıda tutar. Muhasebe/model/SQL'yi kapsar; replay geçmişi Git'te
  korunur. Varsayılan tam
  yerel yedek seçeneği sürer. Gold portföy gözlem ritmi değiştirilmedi.

Gerçek son üretim kapsülü ağsız eski koduyla aynı tek kararı üretti. Yeni kodda
GRAM için yalnız `VERİ BEKLENİYOR/data_block` → `BEKLE/spread_limit` değişti;
yeni dolum 0, sabit girdi hash'i değişmedi. Aynı gerçek defter önekli beş kapsül
3.188.194 byte yerine 700.672 byte saklandı (yaklaşık %78 azalma). Bu örnek,
bütün geçmişin veya gelecekteki büyümenin ölçümü değildir.

Davranış testleri makas/veri ayrımı, stop, retry sınırı, eski/yeni replay,
ortak parça bozulması ve operasyon yedeği geri dönüşünü kapsar.
Ağ/gerçek veri korumaları gevşetilmedi; 37 ortak motor modülü BIST ile eşit.
Güncel sonuçlar `reports/duzeltmeler-2026-10-29/validation.json` içindedir.

Üretim kabulü henüz yapılmadı. Güncel uzak main'e yalnız incelenen kod/test
paketi uygulanacak; eski yerel SQL veya defter yayımlanmayacak. Sonrasında
taze çevrim, defter eşliği, Telegram ve yeni yedek geri dönüşü doğrulanacak.
Ortak deney T0 açılmaz; ücretsiz kotanın gelecekte yeterli olacağı garanti edilmez.

2026-10-29 salt-okunur envanterde 45 eski artifact toplam 10.742.396.316 byte
tutuyor; son tek ZIP 672.227.048 byte. Envanter
`reports/duzeltmeler-2026-10-29/artifact-inventory.json` içindedir. Bunlar
yerelde topluca kopyalanmadı veya buluttan silinmedi. Yeni 3 günlük saklama
ayarı eski artifact'lere geriye dönük uygulanmaz. Public standart runner ve
private kota ayrımı [GitHub resmi belgesindedir](https://docs.github.com/en/billing/concepts/product-billing/github-actions);
hesabın gerçekleşmiş fatura/limiti ayrıca doğrulanmış değildir.
