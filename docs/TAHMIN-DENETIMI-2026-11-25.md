# Altın tahmin ve zamanlama denetimi

25 Kasım 2026 tarihli araştırma, 24 Kasım üretim defterinin ayrı arşiv
kopyasıyla yapıldı. Kaynak SQL'de son teorik gram 23 Kasım, V2 son doğrulanan
standart bildirim 24 Kasım 21.49 ve 418 numaralı. V2 gün sonu teslimi açık.
25 Kasım 01.28 arşiv işi aylık CSV'yi güncelledi.
[Üretim kesiti](https://github.com/Mertsaglm/gold_tracking_system/commit/1bad05fc791c3bc1512ced7327a596189c4b7411)

| Ölçüm | Sonuç |
|---|---|
| 20 seans kur tahmini MAE | Ridge 0,210; 20 seans geçmiş drift 0,241; sıfır değişim 1,595 puan. |
| 20 seans gram MAE | Sıfır 5,902; sıfır ons ve kur Ridge 6,235 puan. Ortak 126 tarih, 7 örtüşmeyen başlangıç. |
| Aynı gün banka zamanlaması | 37 gözlenen gün, 36 eş dolum, 22 farklı saat. Bekleyen kol eşleşen günlerde yaklaşık %0,09 daha ucuz alım fiyatına ulaştı, bir erken kapanışta dolmadı. |
| Günler arası katkı | Bitiş değerleri ilk uygun kolda 48.563,34, bekleyen kolda 48.330,93 TL. Fark tek katkının farklı tarihte alınmasından geldi. |
| Ortak T0 | 24 Kasım gündüzünde çekirdeğin %4 sınırına uyan 32/32 geçerli gözlem var. Canlı kabul ve ortak gelecek tarih açık. |

Yeni deney sözleşmesi raporlama, bildirim ve nöbetçi modüllerini ekonomik
kod özetinden ayırır. Eski sözleşmeler kendi hash kapsamlarını korur.
Bu araştırma dalı üretim takvimini ve karar ayarlarını değiştirmez.
[Ortak sözleşme](../advisor/portfolio_candidates.py) · [Davranış testleri](../tests/test_portfolio_experiments.py)

Ortak araştırmanın kaynak ve model makbuzları erişim yetkisi gerektiren
[BIST denetiminde](https://github.com/Mertsaglm/bist-analiz/blob/codex/forecast-audit-docs-20261125/docs/TAHMIN-DENETIMI-2026-11-25.md).
