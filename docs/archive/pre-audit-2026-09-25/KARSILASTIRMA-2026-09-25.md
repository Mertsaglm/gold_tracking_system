> Tarihsel kopya: bu sayısal sonuçlar yerel denetimle güncellendi. Güncel rapor: `docs/YEREL-DENETIM-2026-09-25.md`.

# Basit rakip ve katkı ölçümü — 2026-09-25

Kullanıcının beş sorusundan çıkan uygulama. Önceki revizyonun üstüne gelir;
üretim yayını yapılmadı. Yalnız sanal portföy ve geçici tarihsel sınav vardır.

## 1. Gerçek karar veren basit rakip

`sma50-v1` ayrı aday defterinde aynı başlangıç ve aylık parayla çalışır.
Son kapanış SMA50 üstündeyse alım adayı; altındaysa/eşitse satış kararı verir.
Ridge çağırmaz, getiri tahmini uydurmaz, kalibrasyon için sahte tahmin kaydetmez.
İlk sinyalden sonraki taze kotasyon, ücret, lot, nakit/pozisyon/sektör ve toplam
stop riski sınırları korunur. Aynı oynaklık temelli koruyucu stop kullanılır.
Hedef fiyat ve zaman çıkışı yoktur. Getiri tahmini olmadığı için tahmine dayalı
kazanç/risk filtresi uygulanmaz: bu, bütün işlem yöntemlerinin karşılaştırmasıdır;
yalnız regresyon katsayılarının karşılaştırması değildir. Deneme tutarı büyütülmez.

## 2. TRALT ve ortak altın ilişkisi

TRALT risk etiketiyle, GRAM doğrudan altın etiketiyle görünür. Panel iki ana hesabın
net değerini ve etiketli pozisyonların toplam payını hesaplar. Aday/benchmark
hesaplar toplama girmez. Hesap kimliği uyuşmazsa, fiyat/değerleme eski veya eksikse
oran gösterilmez. İki kaynak zamanı ayrıca yazılır; eşzamanlı kotasyon iddiası yoktur.
TRALT pozisyonu varsa ortak yoğunlaşma sınırı değerlendirmesi görünür.
Bu bir korelasyon/beta hesabı ve gram eşdeğeri değildir; bilinen etiketleri kapsar.
Sert sınır bu aşamada tanımlanmadı; onaylanan yaklaşım önce ölçüm/görünürlüktür.
İki bütçe arasında transfer ve otomatik ortak risk engeli yoktur.

## 3. Geri çekilme adayının yeterliliği

5 seans Ridge ile aynı modelin geri çekilme giriş kuralı karşılaştırılır.
Ayrıca giriş kuralı sabitken zscore20/range20 yalnız tahmin girdilerinden çıkarılır;
böylece kural etkisi ile tahmin girdisinin etkisi ayrı ölçülür.
range20 son 20 kapanış içindeki konumdur; doğrulanmış destek/direnç seviyesi değildir.
Yeni model ailesi veya destek/direnç motoru eklemek bu deneyin otomatik sonucu
sayılmaz. Bulgular bölümünde elde edilen kanıta göre karar verilir.

## 4. Rejim karşılaştırması

Aynı kontrol stratejisi: piyasa rejimi ayarsız, mevcut V2 ayarı ve BIST'te gerçek
`src/regime.py` sınıflandırıcısı ile sınanır. Sermaye düşüşü/stop/ücret kuralları aynıdır.
V1'in boyut çarpanı, nakit tabanı ve pozisyon sayısı uygulanır; V2 risk tavanları
gevşetilmez. Her karar yalnız önceki kapanışın rejimini kullanır. Eksik/gelecek
zamanlı rejim kaydı hata verir; sessiz başka yönteme dönüşmez.
V1 SMA50 göstergeleri mevcut SQL'in yalnız bellek kopyasında geçmiş fiyatlardan
üretilir. `classify` asıl V1 kodudur; kopya sınıflandırıcı yazılmadı. Sürüm/ayar özeti
raporlanır. Genişlik paydası %80 altındaki günler ayrıca eksik sayılır.
Altın deposunda bu BIST sınıflandırıcısı yoktur: altında V2/ayarsız karşılaştırılır;
BIST rejimi altına taşınmış gibi gösterilmez. Makro geçmişi ve düzeltilmiş fiyatlar
verinin o gün yayımlanan sürümü garantisini vermez.

## 5. Katkı ölçümü

`compare-methods` komutu sabit bir katalog kullanır; parametre araması yapmaz.
Önce yalnız eğitim penceresi, sonra yalnız zaman ağırlığı, sonra ek özellikler
karşılaştırılır. Ek özellikler dört grup halinde çıkarılır. Ardından ufuk ve
aynı ufukta giriş kuralı değiştirilir. BIST30 / BIST30+CCOLA+CIMSA ve iki ek hisseyi
tek tek çıkarma karşılaştırmaları da vardır. Eğitim/göreli özellikler ve işlem
listesi birlikte değişir; yalnız gösterilen liste kırpılmaz.
Her karşılaştırmanın ebeveyni ve değişen unsuru raporda yazılıdır. Geliştirme/son
bölüm net getirisi, en yüksek düşüş, ortalama yatırımda kalma, yükselen al-tut
günlerini yakalama oranı, işlem tutarı ve ücretler görünür. Eksik maliyetler gizlenmez.
Farklar yüzde puandır. Düşüş farkının pozitif olması daha az kayıp demektir.
Yükselen günleri yakalama, al-tutun pozitif günlük getirilerinin olduğu günlerde
yöntemin günlük getiri toplamının al-tut toplamına oranıdır; olasılık değildir,
negatif veya %100 üstü olabilir.
Bir özelliği çıkarmanın etkisi bağımsız nedensel katkı değildir; etkileşimler vardır.
Son bölüm önceki revizyonda zaten görüldü: yeni bağımsız sınav veya başarı kanıtı
olarak sunulmaz. Otomatik kazanan seçimi/terfi yoktur.

## Yeniden çalıştırma

Her proje kökünden:

```bash
python -m advisor compare-methods --start 2025-09-01 --end 2026-09-24 --output /tmp/method-comparison.json
python -m pytest -q tests/test_advisor_comparisons.py tests/test_advisor_revision.py
node --test dashboard/test/*.test.mjs
```

Çıktı `data/` altına yazılamaz. Üretim veritabanı, defter ve banka değişmez.
Bu araştırma elle çalıştırılır; her portföy koşusunda tekrar backtest yapılmaz.


## Doğrulama

2026-09-25: BIST tam suite 1433 geçti; altın tam suite 988 geçti, 8 atlandı.
Atlamalar önceki açıklamadaki yedi CLI'siz yardımcı modül ve altına uygulanmayan
BIST üyelik testidir. Panelde her depoda 10 test geçti. Ortak çekirdek manifesti
32 modülü eşliyor. Yerel tarayıcıda ortak tutar/oran ve SMA50 kuralı görüldü;
JavaScript hata kaydı boştu. Önizleme açıkça test olarak işaretli geçici veriydi.

Davranış kilitleri: tahminsiz SMA50 alımı, trend çıkışı, aynı kotasyonda alımın
beklemesi, eski fiyat ve kapanışta işlem engeli; çıkarılan özellik değişse de
model tahmininin değişmemesi; sınırlı deney kataloğu ve gerçek evren kırpılması;
gelecek/eksik V1 kaydının reddi; ayrı aday bütçeleri ve tahmin olmayan kaydın
kalibrasyona girmemesi; eski/eksik ortak değerlemenin sıfıra dönüşmemesi.


## Gerçek arşiv sonuçları

İstenen aralık 2025-09-01–2026-09-24; iki arşivin kullanılabilir son fiyat tarihi
2026-09-22. Son bölüm 2026-06-01 ile başlıyor. BIST'te 17, altında 13 yöntem
aynı tarihler ve katkılarla çalıştı. Her depodaki ham sonuç:
`reports/KARSILASTIRMA-2026-09-25.json`. Kod özeti son kaynakla eşleşti.
Aşağıdaki getiriler yatırılan yeni paradan arındırılmıştır.

| Yöntem | BIST geliştirme | BIST son bölüm | Altın geliştirme | Altın son bölüm |
|---|---:|---:|---:|---:|
| control | %-0.093 | %+0.000 | %+0.000 | %+0.000 |
| sma50 | %+23.100 | %-4.718 | %-0.162 | %+1.919 |
| window | %+1.384 | %+0.000 | %-1.410 | %+0.424 |
| recency | %+1.002 | %+0.000 | %-1.410 | %-4.100 |
| adaptive | %+1.167 | %-0.070 | %-1.410 | %-4.100 |
| without_pullback | %+0.284 | %+0.181 | %-1.410 | %-4.100 |
| without_short_momentum | %+0.359 | %-0.080 | %-1.410 | %-4.100 |
| without_volatility | %+0.002 | %+0.425 | %-1.410 | %-4.100 |
| without_relative_breadth | %+1.182 | %+0.000 | %-1.410 | %+0.000 |
| short | %+0.214 | %+0.000 | %+0.000 | %+0.000 |
| pullback | %+0.609 | %+0.000 | %+0.000 | %+0.000 |
| pullback_without_shape | %+0.631 | %+0.000 | %+0.000 | %+0.000 |
| regime_none | %-0.575 | %+0.000 | %+0.000 | %+0.000 |
| regime_v1 | %-0.223 | %+0.000 | Uygulanmaz | Uygulanmaz |
| bist30 | %-0.967 | %+0.000 | Uygulanmaz | Uygulanmaz |
| without_ccola | %-0.984 | %+0.000 | Uygulanmaz | Uygulanmaz |
| without_cimsa | %-0.078 | %+0.000 | Uygulanmaz | Uygulanmaz |

Son bölüm ana evren al-tut getirisi BIST −%0,435; altın +%3,171.
BIST her yöntemde strateji/al-tut toplamında dört saklama matrahı bekleyen kayıt
var; DSTKF/TRALT geçmişi yok. BIST getirileri tam maliyet sonrası başarı kanıtı
sayılamaz. Altın makası tarihsel banka kotasyonu yerine %3 varsayımıdır.

### Beş başlığın kapanış kontrolü

| Başlık | Çalışan çıktı / doğrulama | Son karar |
|---|---|---|
| Basit rakip | SMA50 ayrı ileriye dönük hesap + iki gerçek arşiv sınavı + alım/satım/masraf testi | Eklendi; ana model yapılmadı. BIST son bölüm −%4,718, altın +%1,919; istikrarlı üstünlük yok. |
| Ortak altın ilişkisi | TRALT/GRAM etiketi, ana hesap tutarı/oranı, eşleşmeyen veya eski veride bilinmeyen sonuç; tarayıcı kontrolü | Onaylanan görünürlük aşaması tamam. Sert sınır oranı uydurulmadı; ilişkili hisse pozisyonu değerlendirme uyarısı üretir. |
| Geri çekilme yaklaşımı | short/pullback ile giriş kuralı, pullback/pullback_without_shape ile tahmin özellikleri ayrı sınandı | Ridge korundu; destek/direnç motoru için yeterli kanıt yok. |
| Rejim karşılaştırması | BIST V1/V2/ayarsız; altın V2/ayarsız; yalnız geçmiş rejim kaydı | Mevcut V2 kontrolü korundu; V1'e geçiş için üstünlük yok. |
| Katkı ölçümü | Pencere, zaman ağırlığı, dört özellik grubu, ufuk, giriş kuralı, BIST30 ve iki ek hisse için sabit karşılaştırmalar | Mekanizma ve ilk ölçüm tamam; geçmişte iyi görünenlere göre otomatik liste/model seçimi yapılmadı. |

Geri çekilme giriş kuralı BIST geliştirme bölümünde yaklaşık +0,395 yüzde puan
fark verdi; son bölümde iki yöntem de nakitteydi. Geri çekilme tahmininden
zscore20/range20 çıkarılınca geliştirme farkı yalnız yaklaşık +0,022 puan oldu.
Her geri çekilme sürümünde toplam sekiz dolum var; altında hiç dolum yok.
Bu, özelliklerin gereksizliğini veya Ridge'in yeterliliğini kanıtlamaz. Karar:
ölçüm hattı hazır, yeni model ailesi/ek gösterge bu kanıtla eklenmez; ileriye dönük
sonuçlar sürümlü aday hesaplarında birikir. Bu başlık ertelenmiş bir kod işi değildir.

V1 BIST rejimi 267 işlem gözleminde önceki gün girdisi kullandı; yeniden üretilen
genişlik/endeks kapsamı bu gözlemlerde eksik kalmadı. V2 kontrolünün geliştirme
getirisi −%0,093, V1 −%0,223, ayarsız −%0,575 oldu; son bölümde üçü de nakitteydi.
Altında kontrol işlem üretmediği için rejim farkının sıfır olması bilgi sağlamıyor.
Bu sonuçlardan V2'nin kalıcı üstünlüğü çıkarılamaz.

Yakın döneme ağırlık verme altında yalnız pencere kısıtına göre son bölümde
−4,524 puan fark verdi. Yeni özellikler ve daha hızlı uyum otomatik iyileşme değildir.
Bazı özellikleri çıkarmak daha iyi görünse de aynı son döneme tekrar bakıldığı
ve işlem sayısı sınırlı olduğu için canlı yapı geriye dönük optimize edilmedi.

BIST'te iki ek hisse birlikte geliştirme bölümünde kontrole yaklaşık +0,874 puan
katkı verdi. CCOLA çıkarılınca yaklaşık −0,891, CIMSA çıkarılınca +0,015 puan fark
oluştu. Son bölümde ana strateji nakitte olduğu için fark yoktu. Bu, tek hissenin
nedensel getirisi veya gelecekteki katkısı değildir; eğitim ve fırsat evreni birlikte
değişmiştir. İzleme listesi bu geçmiş sonuçla otomatik budanmadı.

Kod, ölçüm, panel ve beş başlığın kabul ölçütleri yerelde tamamlandı. Commit/push
ve üretim yayını henüz yapılmadı; mevcut proje onay kuralı geçerlidir.
