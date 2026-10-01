# Yerel tamamlanma ve eğitim denetimi — 2026-09-25

Commit/push/deploy yapılmadı. Bu rapor önceki aynı tarihli ölçümleri günceller.
Eski karşılaştırma JSON'ları `reports/archive/pre-audit-2026-09-25/` altında korunur.

## Bulunan ve düzeltilenler

1. 2025 takvimi olmadığı için geçmiş sınavda işlem engelleniyor, yine de performans
   raporlanıyordu. 2025 tam/yarım günleri resmi takvimle eklendi; eksik yıl artık
   simülasyon/aday sınavı/katkı karşılaştırması başlamadan hata verir.
   Kaynak: https://www.borsaistanbul.com/resmi-tatil-gunleri (2026-09-25 kontrolü).
2. Son 756 eğitim günüyle fit edilen modelin sayacı bütün olgun arşivi gösteriyordu.
   `training_rows/dates/start/end` gerçek fit penceresidir; `available_training_*`
   arşivdeki kullanılabilir toplamdır. Pozitif/negatif/sıfır etiket sayısı saklanır.
3. Çeyreğin ilk günü tatilse saklama ücreti hesabı önceki seansın bilinen değerini
   unutuyordu. Bilinen değer taşınır; gerçekten eksik seans hâlâ ücret matrahını bekletir.
4. Altın arşivinde gerçek gün içi OHLC yokken tam stop/hedef dolumu varsayılıyordu.
   Artık yalnız sonraki gözlenen günlük referansta çıkış sınanır. Banka gerçek
   dolumu değildir; daha iyi veya daha kötü sonuç vermesi düzeltmenin amacı değildir.
5. BIST sıfır hacimli seans barıyla tarihsel dolum yapılabiliyordu. Referans
   değerleme için korunur, strateji/al-tut ve gün içi satış dolumları engellenir.
6. DSTKF/TRALT geçmişi eksikti. Sağlayıcıdan alındı, mevcut ortak 2026-09-22
   tarihine kadar eklendi. Önceki tüm fiyatlar, kararlar ve sonuçlar tablo bazında
   hash ile korundu. Endeks boşluğu tek başına hisse gününü elemez: mevcut
   `prices.purge_phantom_bars` üçlü kuralı uygulandı. Ham sayılar ve koruma makbuzu
   BIST `reports/VERI-TAMAMLAMA-2026-09-25.json` içindedir.
7. Son veriyle kalıcı aday eğitim paketi yoktu. `train-models` eklendi ve çalıştırıldı;
   gerçek katsayılar, değerlendirme, veri/kod özeti, eski karar kapsamı ve tekrar
   hesaplanabilir tahmin girdileri `reports/MODELLER-2026-09-25.json` içinde saklandı.

## Modeller gerçekten eğitildi mi?

Evet. Her piyasada ana 20 seans Ridge ve üç aday yapılandırması eğitildi.
İki 5 seans adayının katsayıları aynıdır; biri trend, diğeri geri çekilme giriş
kuralını kullanır. Bunlar iki bağımsız tahmin zekâsı değildir. SMA50 öğrenilen
bir model değildir; sabit işlem kuralıdır.

BIST fiyat havuzu 2015-01-02, altın havuzu 2016-01-04'te başlıyor; ortak son veri
2026-09-22. Gelecekte henüz gerçekleşmemiş 5/20 seans getirileri eğitimden çıkarılır.
Ana model tüm geçerli geçmişi; yakın dönem adayları son 756 olgun eğitim gününü,
126 seans yarım ömürle kullanır. Daha eski veriler zaman sıralı değerlendirmede
kalmaya devam eder. Aynı güne ait çok sayıda hisse bağımsız dönem değildir.

| Piyasa / yapılandırma | Gerçek fit satırı | Fit günü | Yükseliş / düşüş / yatay örnek | MAE / basit ortalama MAE (yüzde puan) |
|---|---:|---:|---:|---:|
| BIST / control-20-v1 | 186977 | 2719 | 105122 / 80602 / 1253 | 10.784 / 10.721 |
| BIST / recent-20-v1 | 53493 | 756 | 28035 / 25306 / 152 | 11.153 / 10.789 |
| BIST / recent-5-v1 | 53529 | 756 | 27019 / 26111 / 399 | 4.907 / 4.854 |
| BIST / reversion-5-v1 | 53529 | 756 | 27019 / 26111 / 399 | 4.907 / 4.854 |
| Altın / control-20-v1 | 2383 | 2383 | 1716 / 667 / 0 | 5.289 / 4.862 |
| Altın / recent-20-v1 | 756 | 756 | 603 / 153 / 0 | 6.871 / 5.070 |
| Altın / recent-5-v1 | 756 | 756 | 498 / 258 / 0 | 2.896 / 2.333 |
| Altın / reversion-5-v1 | 756 | 756 | 498 / 258 / 0 | 2.896 / 2.333 |

Bütün yeni Ridge adayları bu tarihsel MAE kıyasında basit ortalamadan kötü.
`approved` kapalıdır. Eğitim tamamlandı, yatırım üstünlüğü kanıtlanmadı.
Ana model ve risk sınırları değiştirilmedi; otomatik model terfisi yok.

Eski AL/SAT kararları doğru hedef olarak ezberletilmedi. Eğitim hedefi gerçekleşmiş
fiyat değişimidir; alınan, alınmayan, yükselen ve düşen geçerli örnekler birlikte
kullanılır. Aynı gün/sembol için tekrar eden LLM kararları örneği çoğaltmaz.
Model paketindeki `legacy_decision_coverage`, eski karar tarihlerinin gerçek fit
penceresinde bulunup bulunmadığını ve olgunlaşmamış/eksik/geçersiz kalanları sayar.
Eski ve yeni modelin farklı ufuktaki sonuçları canlı kalibrasyona karıştırılmaz.

## Gerçek zincir ve yan etkiler

Gerçek SQL arşivinin geçici kopyasında `service.cycle` uçtan uca çalıştırıldı.
Ana hesap + dört aday, ayrı bütçe/defter/model/karar kapsülü üretti; tüm model
kimlikleri eğitim paketiyle eşleşti. BIST 32 isim, altın GRAM gördü. Kotasyon
verilmediğinden işlem açılmadı; 22 Eylül verisi 25 Eylül için güncel sayılmadı.
Bu kontrollü offline doğrulamadır, gerçek zamanlı banka dolumu veya yeni canlı
başarı kaydı değildir. Makbuz: `reports/YEREL-ZINCIR-2026-09-25.json`.

Mevcut `data/advisor` dosyaları bayt bazında değişmedi. Eğitim paketleri araştırma
çıktısıdır; yayımlanmadan mevcut üretim modeli değişmez. İlk yeni cycle güncel
arşivden kendi eğitim/cache sürecini yürütür.

## Yeniden doğrulama

Her depo kökünde:

```bash
python -m advisor train-models --end 2026-09-25 --output /tmp/models.json
python scripts/verify_local_training.py --report /tmp/models.json
python -m advisor compare-methods --start 2025-09-01 --end 2026-09-24 --output /tmp/comparison.json
python -m advisor experiment --start 2025-09-01 --end 2026-09-24 --output /tmp/experiment.json
python -m pytest -q
node --test dashboard/test/*.test.mjs
```

Eğitim doğrulayıcı arşiv, kod ve yapılandırmayı kontrol eder; katsayıları baştan
hesaplar, saklanan tahminleri yeniden üretir, gelecek etiket sızıntısı ve kapsam
paydasını sınar. Eğitim komutu `data/` altına çıktı yazmayı reddeder.

## Kalan gerçek sınırlar

- Sağlayıcının geçmişte düzelttiği fiyatlar ve bugünkü hisse evreni kullanılıyor;
  geçmişte gerçekten bilinen veri sürümü/üyelik eksiksiz değildir.
- Tarihsel İş Bankası alış/satış kotasyonu yok; altında %3 makas varsayımı sürüyor.
  Gerçek emir sırası, kişisel tarife ve MKK masrafları tam doğrulanmış değildir.
- BIST tarihsel temettü ödeme günleri tam değil; tam nakit/lot toplam getiri
  simülasyonu iddiası yok. Bu nedenle getiriler kesin net yatırım getirisi sayılmaz.
- Önceki sınav dönemi görülmüştür; tekrar sınamak yeni bağımsız başarı kanıtı değildir.
- Canlı olgun sonuçlar henüz yeterli değildir. Yeni kapanışlara uyum süresi ile
  yöntemin güvenilirliğinin kanıtlanma süresi farklıdır; hız kazanma sözü verilmez.
- 2027 takvimindeki tahmini bayram kayıtları gelecek yıl öncesi resmi kaynakla
  yeniden doğrulanmalıdır. Yeni gerçek çevrim için arşiv/kotasyon tazeliği gerekir.


## Kapanış doğrulaması — 2026-09-25

- BIST tam suite: **1442 geçti**. Altın tam suite: **997 geçti, 8 atlandı**.
  Atlamalar önceki yedi CLI'siz yardımcı modül ve altına uygulanmayan BIST üyelik testidir.
- Her panelde **10 test geçti**; bu denetimde arayüz kodu değiştirilmedi.
- **33 ortak Python modülü** iki depoda ve manifestte eşleşti.
- Beş yeni koruma bellek içinde kaldırıldığında ilgili regresyon testi düştü;
  kaynak dosyaya bozucu mutasyon yazılmadı.
- Bütün eğitim/aday/katkı raporlarının kod ve veri hash'leri aynı son sürümle eşleşti.
- Gerçek cycle'ın ana/aday model kimlikleri eğitim paketleriyle eşleşti.
- BIST 17 ve altın 13 yöntem sınandı. Takvim eksikliği engeli, izleme evreninde
  eksik fiyat geçmişi ve bekleyen saklama matrahı son sınavlarda **sıfır**.
- Yerel veri 2026-09-22'de biter; geçerli eğitim paketi güncel işlem izni değildir.
- Kontrol makbuzu: `reports/YEREL-DOGRULAMA-2026-09-25.json`.

## Takip doğrulaması — 2026-09-25

Son getiri ayrıştırma turunda altın tam suite yeniden koşulmamıştı. Bu takipte
`.venv/bin/python -m pytest -q` ilk kez **995 geçti, 8 atlandı, 2 başarısız**
verdi. İki hata `tests/test_dokuman_tutarliligi.py:112,119` içindeki STATE
yapı sözleşmesiydi: güncel `ai/STATE.md` başlıkları ve `Kim` sütunu eksikti.
STATE biçimi düzeltildi; tam suite yeniden koşuldu ve **997 geçti, 8 atlandı**.
Son metin eklemesinden sonra yalnız ilgili doküman testleri de **43 geçti**.
İşlem/takvim/dolum kodunda bu takip için değişiklik yapılmadı.
Yukarıdaki BIST **1442** sayısı ilk kapanışın kaydıdır; sonraki BIST
regresyon genişletmesiyle güncel BIST suite **1443 geçti**.
