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



## Düzeltilmiş arşiv sonuçları — 2026-09-25

Takvim, muhasebe, dolum ve veri kapsamı düzeltmelerinden sonra bütün yöntemler
yeniden çalıştırıldı. Önceki sayısal sonuçların yerine bu tablo geçer. Son fiyat
2026-09-22; getiriler katkılar hariç nominal yüzdedir.

| Yöntem | BIST geliştirme | BIST son bölüm | Altın geliştirme | Altın son bölüm |
|---|---:|---:|---:|---:|
| control | -0,813 | -0,719 | +0,000 | +0,000 |
| sma50 | +19,100 | -8,310 | +10,092 | +1,922 |
| window | +0,040 | -0,389 | -2,380 | +0,424 |
| recency | -2,588 | -0,729 | -2,380 | -2,548 |
| adaptive | -0,018 | -1,277 | -2,380 | -2,548 |
| without_pullback | +0,058 | -1,281 | -2,380 | -2,548 |
| without_short_momentum | +0,021 | -1,276 | -2,380 | -2,548 |
| without_volatility | -2,324 | -1,045 | -2,380 | -2,548 |
| without_relative_breadth | -2,240 | -0,727 | -2,380 | -0,000 |
| short | +0,089 | +0,000 | +0,000 | +0,000 |
| pullback | +0,483 | +0,000 | +0,000 | +0,000 |
| pullback_without_shape | +0,510 | +0,000 | +0,000 | +0,000 |
| regime_none | -1,180 | -2,163 | +0,000 | +0,000 |
| regime_v1 | -0,651 | -0,718 | Uygulanmaz | Uygulanmaz |
| bist30 | -1,585 | -0,723 | Uygulanmaz | Uygulanmaz |
| without_ccola | -0,812 | -0,719 | Uygulanmaz | Uygulanmaz |
| without_cimsa | -1,613 | -0,723 | Uygulanmaz | Uygulanmaz |

BIST: son bölüm başlangıcı 2026-06-01, ana evren al-tut %-0,940; toplam bekleyen saklama dönemi 0.
Altın: son bölüm başlangıcı 2026-06-01, ana evren al-tut %+3,267; toplam bekleyen saklama dönemi 0.

Bütün satırlar aynı takvim ve maliyet sözleşmesiyle koştu. Karar kodları, veri
engelleri ve tahmin aralığı artık ham raporda saklanır. SMA50 geçmiş sonuçlarıyla
parametre taranarak seçilmedi; 50 sabit kıyas kuralıdır. Görülmüş dönem tekrar
bağımsız test olarak sunulmaz.

Beş başlığın mekanizması tamam: ayrı SMA50 hesabı, TRALT/GRAM görünürlüğü,
geri çekilme giriş/özellik karşılaştırması, V1/V2/ayarsız rejim ve marjinal katkı
ölçümü. Üstünlük kanıtı yok; ana model değişmedi, yeni gösterge veya model ailesi
bu sonuçlara bakılarak eklenmedi. Sert ortak altın sınırı için oran uydurulmadı.

Aynı getiri, aynı model demek değildir. Altındaki bazı 20 seans adayları farklı
tahminlerle aynı dolumlara ulaşır; kısa adaylarda sıfır getiri, nakitte beklemeyi
ifade eder. Yeni modelin eğitimi ve bütün sınırlar:
`docs/YEREL-DENETIM-2026-09-25.md`. Ham sonuç:
`reports/KARSILASTIRMA-2026-09-25.json`.
