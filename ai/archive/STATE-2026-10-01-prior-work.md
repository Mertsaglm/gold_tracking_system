# 2026-09-25 ve 2026-09-30 yerel çalışma

## Tamamlanan yerel kapsam

- İki ayrı 50.000 TL + aylık 5.000 TL; faizsiz nakit, ayrı yeni hesap kimliği.
- Seans/gözlem/kapanış ayrımı, sonraki taze kotasyonda sanal alım.
- BIST30 + CCOLA/CIMSA tarihli liste; 2026-10-01 DSTKF/TRMET değişimi.
- Piyasa riski, ücret borcu, üç aylık saklama, veri eksikliği ve eski defter korunumu.
- Ana Ridge + yakın dönem 20/5 seans ve geri çekilme; ayrı SMA50 sanal rakip.
- V1/V2/ayarsız rejim, özellik grupları ve ek hisseler için sabit katkı sınavı.
- TRALT/GRAM ortak maruziyet görünümü; aday serveti ana toplama eklenmez.
- Panel, bildirim, nöbetçi, yedek ve ortak çekirdek bağlantıları tamam.

## Son denetimde kapatılanlar

- 2025 takvimi eklendi; eksik yıl sınavı başlamadan reddedilir.
- Fit sayacı gerçek pencereyi gösterir; bütün arşiv sayısı ayrı tutulur.
- Tatilde başlayan çeyrekte bilinen önceki değer taşınır; sahte eksik ücret kalmaz.
- Altın için gün içi hayali stop/hedef dolumu kaldırıldı; sonraki referans kullanılır.
- BIST sıfır hacimli bar değerleme için korunur, dolum üretemez.
- DSTKF/TRALT geçmişi yerel BIST SQL'ine eklendi; önceki kayıtlar hash ile korundu.
- Son yerel veriyle bütün Ridge yapılandırmaları eğitildi; katsayılar tekrar üretildi.
- Eski iyi/kötü karar günleri eğitim kapsamıyla eşleştirildi; AL/SAT doğru hedef sayılmadı.
- Gerçek arşivle geçici tam cycle; BIST 32 isim ve bütün aday hesapları doğrulandı.
- Düzeltilmiş bütün karşılaştırmalar tekrar çalıştı; eski sonuçlar arşivlendi.
- 2026-09-25 takip turunda tam test paketi önce 995 geçti/8 atlandı/2 STATE
  sözleşme hatası verdi; STATE başlık/tablo biçimi düzeltildi ve 997 geçti/8 atlandı.

## 2026-09-30 doğrulaması

- Ortak kapanış, aktif hesap audit'i, SQL kuyruğu ve HTTP/curl test yasağı düzeltildi.
- Gerçek arşiv kopyasında 50.000 TL yeni hesap/dört aday, tekrar ve yedekten dönüş geçti.
- 2026-09-30 testleri: 998 geçti/8 atlandı; panel 10 geçti; 33 ortak modül aynı.
- Rapor: `docs/DUZELTMELER-2026-09-30.md`; üretim eski hesabı hâlâ kullanıyor.

## Önceki kanıt ve dürüst durum

- Ana rapor: `docs/YEREL-DENETIM-2026-09-25.md`.
- Eğitim paketi: `reports/MODELLER-2026-09-25.json`.
- Zincir/kapanış makbuzları: `reports/YEREL-ZINCIR-2026-09-25.json`,
  `reports/YEREL-DOGRULAMA-2026-09-25.json`.
- BIST/altın arşivi 2026-09-22'de bitiyor; bugünün güncel fiyatı sayılmadı.
- BIST güncel 32 isimde geçmiş eksikliği yok; sınavda bekleyen saklama matrahı yok.
- Ridge adayları MAE'de basit ortalamayı yenmedi; onay/otomatik terfi kapalı.
- İki 5 seans adayının tahmin motoru aynı, giriş kuralları farklı. SMA50 eğitilmez.
- Eski `data/advisor` dosyaları değişmedi. Yeni canlı başarı kaydı oluşturulmadı.
- Üretimde önceki sürüm sürüyor; yerel eğitim dosyası yayın/aktivasyon değildir.

## 2026-10-01 yayın öncesi kanıt

- Uzak altın 14:33 UTC: eski hesap 10.000 TL katkı/sıfır işlem; 33 çıktı
  07:02–14:46 UTC (en büyük boşluk 15,3 dk). Özel BIST Safari'de okundu:
  14:46:54 başarılı, 29 çıktı 08:02–14:47 UTC (en büyük boşluk 17 dk).
  İki uzak SQL geçici DB'de incelendi: BIST30 30/30 bar 2026-09-30,
  altın tarih/banka tick'i 2026-09-30, ons/kur OHLC 2026-09-29. Actions
  manuel dispatch + planlı yedek gösterir; dış kaynak kimliği açık.
- Güncel BIST defterinde 7.124, altın defterinde 1.863 olayın hash zinciri ve
  dörder hesabın bağımsız muhasebesi doğrulandı. BIST ana hesap 55.000 TL,
  altın ana hesap 10.000 TL nakitte; ikisinde de ana işlem yok.
- Eski yerel kapsüller (BIST 148, altın 86) sabit ortamda tekrarlandı; altın
  `.venv` pandas/tzdata kilidine eşitlendi. Güncel üretim kapsülleri açık.
