# Mevcut durum

**Güncelleme:** 2026-10-01
**Aktif iş:** İki piyasada yeni kod 2026-10-01'de `main` dalına yayımlandı.
Altın canlı çevrimi ve Telegram teslim makbuzu geçti; BIST ilk yeni koşusu
seans dışı atlandı. Ortak deney T0 kapalıdır; gerçek emir yok.

## 2026-10-01 yeni kapsam ve sınır

- Beş ayrı sanal kol aynı 50.000 TL + aylık 5.000 TL ile çalışır; çekirdek
  model kapısı beklemez, taktik kendi bütçesi/stop riski içindedir.
- Altın ons/kur Ridge ayrı adaydır; ilk offline 126 test gününde temel
  Ridge MAE'sini iyileştirmedi. Otomatik terfi yok.
- Gerçek SQL'nin geçici kopyasında 2026-09-22 kapanışıyla iki kotasyonlu
  tam çevrim, altı defterin bağımsız mutabakatı, tekrar ve yedek geçti. Bu canlı
  fiyat veya ortak T0 kanıtı değildir. Makbuz: `docs/PORTFOY-DENEYI-2026-10-01.md`.
- BIST ile 37 ortak motor modülü eşit; haber ilk görülmesi ileriye dönük
  mühürlenir. `experiment_start_date` hâlâ `null`.
- Eksik BIST30/engelli haftalık satış ve yarım kuruş hataları kilitlendi;
  2026-10-01 suite: BIST 1478, altın 1016 geçti/9 atlandı; panel 12'şer geçti.
- Güncel üretim SQL'leriyle beşer aday/altışar defter provası geçti; TOASO
  karşılaştırma yarım kuruşu düzeltilip davranış testine bağlandı.
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
- Üretim Telegram defterinde BIST için 32, altın için 33 başarılı bildirim
  makbuzu var. Vercel paneli HTTP 200, yetkisiz durum API'si HTTP 401 verdi;
  parolalı veri görünümü henüz sınanmadı.
- Eski veri sınavı 2026-10-01'de yeniden koştu: altın raporu birebir aynı;
  BIST'e sonradan eklenen dört test satırı ayrı makbuzda saklandı.
- [Altın canlı koşusu](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/36901918911)
  başarılı; Telegram `message_id: 320`. [BIST koşusu](https://github.com/Mertsaglm/bist-analiz/actions/runs/36901914212)
  başarılı fakat seans dışı atlandı. Vercel'in üç statik dosyası yeni sürümle eş.

## Önceki yerel çalışma

2026-09-25 ve 2026-09-30 kapsamı/kanıtları: `ai/archive/STATE-2026-10-01-prior-work.md`.

## Sıradaki 3 İş

1. 2026-10-02 seansında iki piyasanın yeni kodla taze çevrimlerini,
   Telegram makbuzunu ve 2026-10-01 kapanış verisini doğrula.
   DoD: geçerli veri, atlanmamış çevrim ve eski defter eşliği.
2. Koşullar geçince ortak gelecek işlem günü T0'ı iki ayarda sabitle.
   DoD: BIST30 30/30 fiyat, GRAM ve beş ayrı hesap ilk çevrimde mutabık.
3. Parolalı Vercel görünümünü ve 20/63/126 seans değerlendirmesini izle.
   DoD: panel iki yeni hesabı gösterir; sonuçlar pasif kolla maliyet sonrası kıyaslanır.

## TAKVİM

| Tarih | İş | Kim | Durum |
|---|---|:--:|---|
| 2026-09-25 | Yerel düzeltme/eğitim/yeniden sınav | 🤖 | Tamam |
| 2026-09-30 | Üretim sonrası yerel düzeltme ve yayın hazırlığı | 🤖 | Tamam; yayın bekliyor |
| 2026-11-25 | GC=F roll etkisi ve bağımsız prim/FRED kapsamı incelemesi | 🤖 | Bekliyor |

## SENDE KALANLAR

- 👤 Üretim yayını 2026-10-01 kullanıcı onayıyla tamamlandı; parolalı Vercel görünümü için kullanıcı oturumu gerekir.
- İlk yeni BIST seans içi çevrim ve ortak T0 hazırlığı sürüyor.

## Backlog / açık dış bağımlılıklar ve sınırlar

- Tarihsel banka kotasyonu/emir sırası, kişisel tarife ve MKK ücretleri.
- Geçmişte bilinen üyelik/fiyat sürümü, temettü ödeme günü, revizyon geçmişli TÜFE.
- Dış 15 dakika tetikleyicisi ve alıcıya Telegram tesliminin bağımsız kanıtı.
- 2027 tahmini takvim kayıtlarını yıl başlamadan resmi kaynakla doğrulama.
- Aday kapsüllerinin büyümesini gözle; geçmiş kanıtı silmeden saklama politikası.
- Önceki arşiv: `ai/archive/STATE-2026-09-25-before-wealth-revision.md`.
