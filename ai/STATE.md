# Mevcut durum

**Güncelleme:** 2026-10-01
**Aktif iş:** Yerel %80 GRAM çekirdek/%20 taktik sanal sınavı kuruldu;
önceki üretim düzeltmeleriyle birlikte yayın incelemesi bekliyor. T0 kapalıdır.
Üretim yayını ayrı onay bekliyor; gerçek emir yok.

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
- Üretim Telegram defterinde BIST için 31, altın için 32 başarılı bildirim
  makbuzu var. Vercel paneli HTTP 200, yetkisiz durum API'si HTTP 401 verdi;
  parolalı veri görünümü henüz sınanmadı.

## Önceki yerel çalışma

2026-09-25 ve 2026-09-30 kapsamı/kanıtları: `ai/archive/STATE-2026-10-01-prior-work.md`.

## Sıradaki 3 İş

1. 👤 İki depodaki `codex/portfolio-research` dalı için üretim yayın kararını ver.
   DoD: üretim kapsamı ve geri dönüş adımı açıkça onaylanır.
2. Yayın onayıyla yayımla; taze GRAM/BIST çevrimi, Telegram
   bildirimi, parolalı panel verisi ve yedeği denetle.
   DoD: beş kol/ana hesap ayrı, tekrar ve yedek eş.
3. Taze veri ve iki başarılı çevrimden sonra ortak gelecek T0'ı aç.
   DoD: 20/63/126 seans takvimi ve hesap hash'leri kayıtlı.

## TAKVİM

| Tarih | İş | Kim | Durum |
|---|---|:--:|---|
| 2026-09-25 | Yerel düzeltme/eğitim/yeniden sınav | 🤖 | Tamam |
| 2026-09-30 | Üretim sonrası yerel düzeltme ve yayın hazırlığı | 🤖 | Tamam; yayın bekliyor |
| 2026-11-25 | GC=F roll etkisi ve bağımsız prim/FRED kapsamı incelemesi | 🤖 | Bekliyor |

## SENDE KALANLAR

- 👤 Üretim yayını için ayrı açık onay; commit/push 2026-10-01 kullanıcı talebiyle yetkilendirildi.
- Yayın yetkisi verilirse ilk gerçek güncel çevrimde taze veri ve eski defter eşliği doğrulanır.

## Backlog / açık dış bağımlılıklar ve sınırlar

- Tarihsel banka kotasyonu/emir sırası, kişisel tarife ve MKK ücretleri.
- Geçmişte bilinen üyelik/fiyat sürümü, temettü ödeme günü, revizyon geçmişli TÜFE.
- Dış 15 dakika tetikleyicisi ve alıcıya Telegram tesliminin bağımsız kanıtı.
- 2027 tahmini takvim kayıtlarını yıl başlamadan resmi kaynakla doğrulama.
- Aday kapsüllerinin büyümesini gözle; geçmiş kanıtı silmeden saklama politikası.
- Önceki arşiv: `ai/archive/STATE-2026-09-25-before-wealth-revision.md`.
