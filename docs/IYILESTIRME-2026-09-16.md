# Öncelik ve uygulama planı — 2026-09-16

Kullanıcı dört gruptan ilk üçünün uygulanmasını istedi. Önceki rapordaki 25 ve
26 numaralı bakım önerileri tek maddede birleştirildi; toplam 25 madde korundu.
Sıralama: sessiz yanlış para hesabı > yanlış başarı ölçümü > anlaşılabilirlik >
isteğe bağlı kullanım kolaylığı. Hesaplar ayrı; gerçek emir ve geçmiş kayıt değişikliği yok.

Her satır 1–2 saatlik bir çalışma paketi; geniş araştırma işleri kaynak desteği,
mekanizma, uçtan uca doğrulama adımlarında tamamlanır. Aynı anda bir paket uygulanır.

| Grup | Önceki madde | İş | Bitti tanımı |
|---|---|---|---|
| 1 — Güvenlik | 1 | Stop kontrolü | Eski analiz + güncel fiyat stopu işler; geçersiz fiyat/kurumsal belirsizlik işlemi engeller. |
| 1 | 2 | Değerleme güncelliği | Bayat fiyat güncel getiriye/risk bütçesine giremez; son bilinen değer ayrı görünür. |
| 1 | 3 | Ortak takvim | Yarım günün açık bölümü ve seans bazlı vade davranış testini geçer. |
| 1 | 4 | V2 nöbetçisi | Atlanan/başarısız koşu, eksik fiyat ve teslim ayrı salt-okur bulgular üretir. |
| 1 | 5 | Al-tut nakdi | Eksik bir hisse diğerini durdurmaz; lot artığı sonraki katkıyla birleşir. |
| 1 | 6 | Panel CI | Node test/build CI'da çalışır; bozuk bir hesap sağlam hesabı bozamaz. |
| 1 | 14 | Toplam risk | Stop riski ve ortak düşüş senaryosu görünür; toplam yeni risk sınırla korunur. |
| 1 | 24 | Kurtarma | Ayrı arşivden geçici dizine geri dönüş defter/hash/hesap eşliğiyle sınanır. |
| 2 — Ölçüm | 7 | Portföy geçmiş testi | Aynı muhasebe/karar hattıyla nakit, lot, katkı, çıkış ve maliyet işlenir. |
| 2 | 8 | İşlem gerçekleşme stresi | Fiyat boşluğu, satılamama, eksik kotasyon ve gecikme senaryoları ölçülür. |
| 2 | 9 | Fiyat/masraf arşivi | Kaynak, zaman, alış/satış, masraf ayarı ve gözlem farkları sürümlü kaydedilir. |
| 2 | 10 | Temettü mutabakatı | Kanıt referanslı ödeme bir kez alacağı nakde çevirir; servet değişmez. |
| 2 | 11 | Başarı kanıtı | Bağımsız dönem + güven alt sınırı olmadan risk bütçesi büyümez. |
| 2 | 12 | Model karşılaştırması | Sabit/günlük model ayrı gölge hesaplarda ve aynı olgunlaşmış tarihlerde kıyaslanır. |
| 2 | 13 | Tarihsel evren | Tarihli üyelikler o gün bilinen bilgiyle seçilir; eksik geçmiş dürüstçe etiketlenir. |
| 3 — Açıklama/bakım | 15 | Karar kartı | Adet/tutar/masraf/hedef/stop riski tek kartta görülebilir. |
| 3 | 16 | Karar değişimi | Önceki kararla değişen fiyat, model ve eylem açıkça listelenir. |
| 3 | 17 | Bekleme dağılımı | Veri/model/fırsat/bütçe sebeplerinin sayısı tam paydaya eşittir. |
| 3 | 18 | Haftalık V2 özet | Katkı, sonuç, masraf ve al-tut farkı aynı zaman penceresinde hesaplanır. |
| 3 | 22 | Kod eşliği | İki projede ortak kod manifesti doğrulanır; test eski eş dosyayı yakalar. |
| 3 | 23 | Yeniden üretim | Mühürlü girdi+model+ayar+kod paketi karar yolunu tekrar üretir. |
| 3 | 25+26 | Sürümler/doküman | Çalışma bağımlılıkları kilitlenir; komutlar, durum ve sınırlar güncellenir. |
| 4 — Sonra | 19 | Panelden ayar | Bu tur kapsam dışı: ileride tarihli ve doğrulanan ayar arayüzü. |
| 4 | 20 | Gerçek işlem günlüğü | Bu tur kapsam dışı: gerçek işlemleri sanal hesaptan ayrı takip. |
| 4 | 21 | Senaryo ekranı | Bu tur kapsam dışı: araştırma motoru üzerine etkileşimli arayüz. |

## Veri sınırları

Tarihsel banka kotasyonu, kişisel ekstre ve tarihsel evren kaynağı elde yoksa
desteklenen dosya biçimi/denetim kurulur; sahte tarih veya ödeme yazılmaz.
Tam portföy simülasyonunun mekanik doğruluğu, getiri üstünlüğü kanıtı değildir.
Yayın ve gerçek Telegram teslimi bu yerel uygulamanın dışında ayrıca doğrulanır.

## Uygulama durumu

İlk üç gruptaki 22 madde yerel kod, test ve işletim tanımlarıyla uygulandı.
Dördüncü grubun üç maddesi ertelendi. Kaynak gerektiren tarihsel üyelik, gerçek
masraf ve temettü ödeme verileri için doğrulanan içe alma mekanizmaları hazır;
mevcut olmayan kanıtlar üretilmedi. Yayın/canlı çalışma bu turda yapılmadı.

Doğrulama ve sınırlar: [uygulama raporu](../reports/IYILESTIRME-2026-09-16.md).
