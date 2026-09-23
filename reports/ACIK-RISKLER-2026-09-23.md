# Açık risk aksiyonu — 2026-09-23

Bu belge 2026-09-22 üretim denetiminin devamıdır. İnceleme salt-okunur GitHub
arşivine ve onun geçici kopyalarına dayanır. Yerel kod değişiklikleri henüz
commit/push edilmediğinden üretim davranışını değiştirmiş sayılmaz.

## Karar zincirine doğrudan etki eden risk

2026-09-23 sabahı altının uzak SQL arşivinde son `history_daily` tarihi
2026-09-21, EVDS USD/TRY tarihi 2026-09-22 idi. Son V2 görünümü ise günlük
işten önce üretildiği için 2026-09-18 analizini gösteriyordu. Günlük üretici
aynı günün yarım GC=F barını haklı olarak dışlıyor; onu takip eden V2 koşusu
mesai dışında kaldığından ertesi seansa eksik kapanışla girilebiliyor.

Yerel düzeltme iki parçalıdır:

- Altının V2 workflow'u karar öncesi `src.advisor_refresh` çalıştırır. Uzak
  SQL'i geçici DB'ye açar, eksik USD/TRY gerekiyorsa çeker, mevcut GC=F
  kaynağını koruyarak önceki tamamlanmış barı yeniler. Ancak beklenen **tam
  tarih** oluşursa SQL'i hedef dizinde atomik değiştirir. Kaynak başarısızsa
  mevcut SQL baytları korunur.
- BIST ve altın ortak karar kapısı, önceki işlem gününün kapanışı eksikse
  yeni sanal alımı `VERİ BEKLENİYOR` yapar. Mevcut pozisyonun stop/hedef
  takibi sürer. Gölge model karnesine aynı eski veriden yeni tahmin yazılmaz;
  vadesi dolmuş eski tahminlerin çözümü sürer. Eksiklik panel, Telegram
  durum değişimi ve nöbetçide görünür.

Gerçek üretim SQL'inin geçici kopyasında 2026-09-23 10:17 TR için aynı
sentetik banka kotasyonuyla iki uçtan uca koşu yapıldı: eski SQL → analiz
2026-09-21, beklenen 2026-09-22, `VERİ BEKLENİYOR`, 0 fill; gerçek GC=F
çekilip yenilenen SQL → analiz 2026-09-22, sağlık sorunu yok, karar motoru
çalışıyor. İkinci koşuda `AL` ve 1 sanal fill çıkması **yatırım önerisi
değildir**: kotasyon gerçek banka fiyatı değil, kapının açık/kapalı farkını
ölçen test girdisidir. Üretim defteri ve üretim SQL'i değiştirilmedi.
İki kopyanın `history_daily` satırı 2601 → 2602 oldu; `evds_daily` 7860,
`predictions` 234, `prediction_outcomes` 98 ve `reports` 75 satırda kaldı
(2026-09-23 ölçümü). Yani yenileme geçmiş tahmin/sonuç/rapor tablolarını
yeniden kurarken korudu.
Tüm 12 SQL tablosunun sıralı satır SHA-256 özeti de karşılaştırıldı:
yalnız `history_daily` değişti, diğer 11 tablonun sıralı satır özeti eşti.

Regresyon testleri taze/eski/gelecek tarihli barı, yenilemede arşivin bayt
eşliğini, açık stopu, gölge tahmin kaydının tazeliğini ve iki proje arasındaki
ortak motor hash eşliğini sınar.
İki projenin tam testleri ve panel kontrolleri 2026-09-23'te yeniden koşturuldu.

## Koşu sürekliliği

2026-09-21/22 gün içi 15 dakikalık koşuların GitHub tetik türü
`workflow_dispatch`; çağıran servis bu makinede doğrulanamadı. İki V2
workflow'una 10:17–17:17 TR aralığında nominal 30 dakikalık `schedule`
yedeği eklendi. Salt-okur nöbetçi yaklaşık 30 dakikada bir çalışacak ve
son gerçek seans çevrimi 45 dakikadan eskiyse uyaracak; seans dışı koşu bu
kontrolü temizleyemez. [GitHub'ın resmi dokümanı](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows)
scheduled workflow'ların gecikebileceğini veya düşebileceğini söylüyor.
Bu yüzden 15 dakika kesin teslim süresi iddiası yoktur. İlk yayımlanan
üretim seansında gerçek aralıklar tekrar ölçülmelidir.

## Beklemeye alınan veya dış kanıta bağlı riskler

- Canlı 20 seanslık sonuç, satış/stop ve aylık katkı henüz oluşmadı; sentetik
  test bunların istatistiksel kanıtı değildir. Yalnız olgunlaşınca ölçülecek.
- Telegram makbuzu bot API kabulünü kanıtlar; alıcı ekranında görüntülenmeyi
  kanıtlamaz. 15 Eylül sonrası kullanıcı dışa aktarımı yok.
- Kişisel banka tarifesi, dönemsel saklama ücretleri, tarihsel banka makası
  ve BIST tarihsel üyeliği için güvenilir kayıt yok; getiri iddiasına dahil
  edilmedi. V1 altın prim/FRED boşluğu V2 öğrenme kanıtı değildir.
- Panelin canlı deployment'ı ve yeni kodun ilk üretim çevrimi bu yerel
  doğrulamanın kapsamında gerçekleşmedi. Yayın sonrası makbuz/defter
  karşılaştırması zorunlu.

**Güvenlik hükmü:** Bu değişiklikler yayımlanıncaya kadar eski kapanışla
olası yeni alım riski üretimde açık. Yayımlandıktan ve ilk gerçek çevrim
doğrulandıktan sonra sistem yalnız **sanal izleme** için makul; gerçek emir
veya kanıtlanmış getiri kararı için yeterli kanıt yok.
