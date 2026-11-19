# Mevcut durum

**Güncelleme:** 2026-11-18 akşamı (İstanbul).
BIST kapanış arşivi güncel. Seans içinde BIST çevrimi eksik kaldı.
Altının akşam veri boşluğundan sonra taze banka fiyatı doğrulandı.

## Tamamlananlar

- 2026-11-19: BIST 10.17 çevriminde 33/33 fiyat ve karar; altın 11.01
  çevriminde taze GRAM fiyatı. GitHub kaynak verisi panel şemasından geçti.
  İki arşivde de aktif kararla eşleşen Telegram makbuzu doğrulandı.
  Bulut telafisi iki deponun kendi GitHub Actions işinde yürütülür.

- 18 Kasım BIST: 73/73 hisse, USD/TRY ve dört endeks 18 Kasım kapanışına ulaştı.
  19.32 değerlemesinde 33/33 fiyat, Telegram makbuzu 277. İşlem aralığında
  sıfır çevrim; 32 girdisiz dispatch tasarım gereği atlandı. Geçmişe işlem yazılmadı.
- Altın: 18.34 nöbetçisi 45 dakikayı aşan arayı bildirdi. 21.41 telafi çevrimi
  taze GRAM fiyatı ve BEKLE kararı üretti. İki FRED serisinde zaman aşımı var.
- Kapanışın eksik seansı gizlemesini önleyen ortak nöbetçi kontrolü ve
  regresyon testleri eklendi. BIST zamanlamasının kalıcı çözümü açık.


- BIST USDTRY 2026-10-22'de donmuştu: tarihsel tek bozuk satır tüm batch'i
  reddediyordu. Sağlam satırlar ilerler, retler ayrı görünür; güncel eksik
  veya bozuk kapanış başarısız kalır. V1 ve V2 tüketicileri düzeltildi.
- Gerçek Yahoo çekimi yalnız geçici üretim kopyasında: 18 bozuk kaynak
  tarihi ayrıldı, beş endeks/kur 2026-11-17'ye ulaştı. Üretim SQL değişmedi.
- Kapanış değerlemesindeki yanlış veri/saat tanısı iki ortak motorda düzeltildi;
  bayat fiyat engeli ve dolum yasağı davranış testinde korundu.
- BIST 1508 test geçti; Gold 1025 geçti/12 atlandı. Ortak 37 modül eş.
- Güncel SQL: BIST 208.982 bar/73 sembol, altın 2.640 tarih; integrity başarılı.
- 26 fold/126 tarih offline sınav: BIST LightGBM rank IC 0,1213, Ridge -0,0120;
  altın ons/kur ek özellikleri MAE'yi artırdı. Canlı terfi yapılmadı.

## Açık bulgular ve kanıt sınırı

- 18 Kasım kapanışında USDTRY ve değerleme doğrulandı; seans içi ritim açık.
- Altın 2026-11-17 sabah kaynak kimliği hatası, ardından toparlanma doğrulandı;
  başarısız yanıtın gövdesi yok, kök neden DOĞRULANMADI. Kontrol gevşetilmedi.
- Altın dış tetikleyicide 14:45–15:58 UTC boşluğu; nöbetçi doğru alarm üretti.
  Dış scheduler arızasının nedeni DOĞRULANMADI; cron zaman garantisi yok.
- BIST 16 Kasım gecikmesi son SQL'de 73/73 ile toparlandı; ilk eksikliğin
  nedeni DOĞRULANMADI. Ekim kota engeli bugünkü koşulara taşınmaz.
- Arşivde 61 eski USDTRY OHLC ihlali; bağımsız kaynak olmadan onarılmadı.
- BIST data/advisor uzak Git ağacı 3.349.042.744 byte; geçmiş silinmedi.
- İki canlı model approved=false, tamamlanmış strateji roundtrip 0.
  Offline sıralama başarısı net portföy üstünlüğü değildir; otomatik T0 yok.

## Sıradaki 3 İş

1. 19 Kasım açılışından itibaren BIST gerçek işlem çevrimini ve altın sürekliliğini izle.
   DoD: işlem penceresindeki zaman damgalı geçerli fiyat/karar, 90/45 dk
   boşluk kontrolü ve kapanış makbuzu; saatlik dış tetikleyici ayarı doğrulanmalı.
2. Dış scheduler ve kaynak kesintisini bağımsız izle; arşiv büyümesini çöz.
   DoD: tetikleyici saatleri ile runner saatleri ayrılmış, kaynak hata sınıfı
   doğrulanmış; saklama değişikliğinde eski kanıtın geri dönüşü korunmuş.
3. BIST LightGBM adayını aynı maliyetli tam portföy/stop sınavında değerlendir.
   DoD: zaman sıralı bağımsız sınav, pasif kıyas, düşüş ve işlem sayısı;
   ardından iki piyasa kabulüyle ortak ileri T0 ayrı değerlendirilir.

## TAKVİM

| Tarih | İş | Kim | Durum |
|---|---|:--:|---|
| 2026-11-18 | Yerel düzeltmelerin yayın onayı ve canlı kabul | 🤖 | Mert yayın onayını verdi. Canlı koşu izlenecek |
| 2026-11-25 | GC=F roll, bağımsız prim/FRED kapsamı | 🤖 | Bekliyor |

## SENDE KALANLAR

- 👤 Mert yayın onayını 2026-11-18 tarihinde verdi.

## Backlog

- D-01 BIMAS tarihsel düzeltme, erken Ekim telafi kayıpları ve kaynak
  revizyonları önceki kayıtta açık; yeni denetim bunları kapatmıyor.
- Geçmiş üyelik, banka kotasyonu/emir sırası, kişisel tarife/MKK, temettü
  ödeme günü ve revizyon geçmişli TÜFE sınırları devam ediyor.
- 2026-11-25: GC=F roll ve bağımsız prim/FRED kapsamı incelemesi.
- 2027 tahmini takvim resmi kaynakla doğrulanmalı.
- Ayrıntılı önceki kayıt: `ai/archive/STATE-2026-11-17-before-audit.md`.
- Bu deponun işletim ve kabul rehberi `docs/ISLETIM-2026-11-18.md`.
