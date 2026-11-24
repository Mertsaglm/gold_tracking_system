# Mevcut durum

## Devir kontrolü — 2026-11-25

25 Kasım seans öncesi GitHub, SQL ve iki defter yeniden doğrulandı.
Son doğrulanan finansal çevrimler 24 Kasım.
Araştırma inceleme dalına gönderildi. [İlk paket `da41461`](https://github.com/Mertsaglm/gold_tracking_system/commit/da414615e5f0f3a7f41559663e6c0928874a1fa3).
Üretim kaynağı `main`. Canlı kabul ayrıca ölçülür.

| Konu | Son doğrulanmış durum |
|---|---|
| BIST üretimi | `591cb3a` arşivi. 24 Kasım 21.54 V2 33/33, Telegram 304 kapanış makbuzu defterle eşleşti. Telafi adımı SQL 71/73 yüzünden başarısız, BIST30 30/30 ve beş kur/endeks serisi tam. |
| Altın üretimi | `76b8dd2` arşivi. 24 Kasım 21.49 V2 1/1, standart Telegram 418 defterle eşleşti. V1 günlük raporu başarılı. Teorik arşiv 23 Kasım, V2 gün sonu makbuzu açık. |
| Araştırma | 30 BIST30 momentum sırası 24 Kasım 21.50 mühürlü; vade 22 Aralık. Portföy ilk uygun 25 Kasım veya sonraki seansı bekliyordu. Ortak T0 kapalı. Altın ileri zamanlama ve BIST tek değişkenli trend/R:R kolları sırada. |
| Tahmin araştırması | Ayrı 5/20/60 seans CPU koşusu tamamlandı. Altında sıfır getiri MAE'de üç ufukta önde. Kotasyon replay'inde ilk uygun kol 48.563,34 TL, dar makası bekleyen kol 48.330,93 TL. [Kanıt](../docs/TAHMIN-DENETIMI-2026-11-25.md) |
| Ek denetim | 24 Kasım gündüzü %4 çekirdek sınırı 32/32. Gün içi deneyde 36 eş dolum, 22 farklı saat. 25 Kasım 01.28 arşiv işi CSV'yi güncelledi; SQL/defter aynı. Sözleşme düzeltmesi yerel. [Kanıt](../docs/TAHMIN-DENETIMI-2026-11-25.md) |
| Yerel paket | Momentum/pasif hisse ve nakit payı, haftalık ortalama ve gün sayısı, stop ve stres ölçümleri. BIST OHLC reddinde dört ham değer. Üretim yayını bekliyor. Her depoda 5 hedefli test, BIST'te 30 fiyat/telafi testi, 39 ortak modül eş. |
| Veri İzleme | Vercel canlı dosyası doğrulandı. Parolalı oturum, altın otomatik gün sonu makbuzu ve yeni haftalık teslim açık. |
| Kapasite | 24 Kasım aktif artifact: BIST 9 / 496 MB, altın 32 / 6,21 GB. Git defterleri 66,6 / 8,0 MB. BIST örnek günlük koşusu 4 dk 36 sn, V2 telafisi 3 dk 28 sn, CI toplamı 3 dk 48 sn. Hesap faturalama erişimi yok; kalan kota bilinmiyor. |

ARCLK ve SELEC, V1 canlı evreni, V2 izleme evreni ve BIST30 dışında.
Aynı Yahoo istemcisinin sonraki okuması iki barı da doğruladı. Üretimde
reddedilen ilk ham değerler olmadığından kök neden doğrulanmadı.

[BIST V2](https://github.com/Mertsaglm/bist-analiz/actions/runs/45464353034) ·
[BIST CI](https://github.com/Mertsaglm/bist-analiz/actions/runs/45464429266) ·
[Altın çevrimi](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/45463521929) ·
[Altın telafisi](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/45464093885) ·
[Altın günlük raporu](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/45464140195) ·
[Mühürlü momentum](https://github.com/Mertsaglm/bist-analiz/blob/7e19f7e3c369fd9c961f1258fac5efd750e68ca9/reports/champion-challenger-2026-11-24/bist-momentum-forward.json)

Önceki çalışma ve ölçümler [24 Kasım denetiminde](../docs/DENETIM-2026-11-24.md),
[portföy deneyinde](../docs/PORTFOY-DENEYI-2026-10-01.md) ve
[işletim rehberinde](../docs/ISLETIM-2026-11-18.md).

## Açık bulgular ve kanıt sınırı

- 20 Kasım: BIST 8/9 işlem çevrimi, kapanış Telegram 286 dışa aktarımla
  eşleşti. 21.54 AGHOL veri uyarısı gerçek. Altında 33/33 fiyatlı çevrim var,
  sonuncusu 18.26. Geciken işler hafta sonu sebebiyle atlandı, kapanış yok.
- 24 Kasım: 1.189 giriş kararı. 573 makas, 572 fırsat/filtre, 44 veri
  engeli. Son GRAM fiyatı geçerli, makas %3 sınırının üstünde. Olgunlaşan
  17 varsayımsal fırsat koşulu alımı nakdi geçmedi. Makas grubunda vade açık.
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
- 25 Kasım yerel paketinde 1.049 test geçti, 14 atlandı. 39 ortak modül eş.

## Sıradaki 3 İş

1. Üretim kapanışını ve ilk ileri momentum çevrimini doğrula.
   DoD: Son SQL tarihi, fiyat kapsamı, ilk katkı/dolum ve kapanış makbuzu.
2. Yerel ölçüm paketini yayın ve canlı kabul açısından takip et.
   DoD: Eş pasif maruziyet, nakit, stop ve örneklem paydası haftalık görünür.
3. Altın katkı zamanlamasını ayrı ileri portföy olarak takip et.
   DoD: Ayrı kimlik, eş katkı ve ilk uygun kotasyon. Gram, net değer,
   bekleme süresi ve kaçan fiyat hareketi aynı gözlemde karşılaştırılır.

## TAKVİM

| Tarih | İş | Kim | Durum |
|---|---|:--:|---|
| 2026-11-20 | İlk günlük Telegram canlı kabulü | 🤖 | BIST geçti, altın eksik |
| 2026-11-25 | GC=F roll, bağımsız prim/FRED kapsamı | 🤖 | Bekliyor |

## SENDE KALANLAR

- 24 Kasım: Mert önceki paket için commit, push ve üretim yayınına onay verdi.
  25 Kasım tahmin araştırması inceleme dalında izlenir. Ortak T0 ve altın V2 kapanış kabulü açık.
- 2026-11-19: Mert yayın onayı verdi. Üretim `98ce9fa` ile güncellendi.
  19 Kasım yeni işletim dönemi başlangıç kesiti. Eski defterler korunuyor.
- 👤 Mert yayın onayını 2026-11-18 tarihinde verdi.

## Backlog

- D-01 BIMAS tarihsel düzeltme, erken Ekim telafi kayıpları ve kaynak
  revizyonları önceki kayıtta açık; yeni denetim bunları kapatmıyor.
- Geçmiş üyelik, banka kotasyonu/emir sırası, kişisel tarife/MKK, temettü
  ödeme günü ve revizyon geçmişli TÜFE sınırları devam ediyor.
- 2027 tahmini takvim resmi kaynakla doğrulanmalı.
- Ayrıntılı önceki kayıt: `ai/archive/STATE-2026-11-17-before-audit.md`.
- Bu deponun işletim ve kabul rehberi `docs/ISLETIM-2026-11-18.md`.
