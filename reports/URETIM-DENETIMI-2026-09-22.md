# 15 Eylül revizyonu sonrası üretim denetimi — 2026-09-22

**Hüküm:** Para muhasebesi ve mühürlü karar izi sağlam bir temel veriyor. Üretimde
yaşanmış bildirim/mutabakat hataları ve veri kapsamını sessizce daraltabilecek yollar
vardı; düzeltildi ve kopya arşivlerde sınandı. Bu rapor, yayımdaki sistemin düzeldiği
anlamına gelmez: değişiklikler henüz commit/push/deploy edilmedi. Gözetimsiz güvenilir
işletim ve gerçek para kullanımı için yeterli kanıt yok. Düzeltmeler yayımlandıktan
sonra, aşağıdaki veri sınırları görünür tutularak sınırlı sanal deneye devam edilebilir.

## Kanıtın sınırı ve kaynağı

Proje hafızasına güvenilmedi; GitHub'daki son üretim arşivleri ayrı dizinlere indirildi.
BIST `253501683a340c35099096fda0f1ed5a94e3ab6e`, altın
`c12ecd43e836d02b1a8c8a982074a10e403558e7` sabit kaynakları kullanıldı. İnceleme
2026-09-15–2026-09-22 dönemini kapsar. Son görünüm saatleri sırasıyla
2026-09-22 17:31:03 ve 17:31:13 Türkiye saatidir. GitHub koşuları, SQL dump'ları,
olay defterleri, model dosyaları, karar kapsülleri, günlük raporlar, loglar ve eldeki
Telegram dışa aktarımları çapraz okundu. Yerel BIST arşivi üretimin gerisindeydi.

Makine kanıtları: [BIST](URETIM-DENETIMI-2026-09-22-bist.json),
[altın](URETIM-DENETIMI-2026-09-22-gold.json). Sayılar bu kesit için ölçümdür.
Ham üretim SQL/defterlerine yazılmadı. Başlangıç kopyasıyla karşılaştırılan BIST 75,
altın 84 mevcut veri dosyası değişmedi. Mutabakat onarımı yalnız geçici DB'de denendi.

**Telegram sınırı:** Elde bulunan BIST dışa aktarımı revizyon günü yalnız 01:43'teki
eski nöbetçi mesajına kadar, altın dışa aktarımı 2026-09-14'e kadar geliyor.
Revizyon sonrası alıcı ekranını bu dosyalardan doğrulamak mümkün değil. Defterdeki
başarılı API makbuzu, kullanıcının mesajı gördüğünün kanıtı değildir. Yeni makbuzlar
`message_id`, Telegram zamanı ve kaynak görünüm hash'ini de saklıyor. Denetimde
gerçek mesaj gönderilmedi.

## Verinin doğruladığı güçlü noktalar

| Kontrol | BIST | Altın |
|---|---:|---:|
| Hash zinciri doğrulanan olay | 1.965 | 483 |
| Kayıtlı kod/runtime ile birebir tekrar üretilen kapsül | 72 | 71 |
| Güncel motorla karşılaştırılan kapsül içi karar | 1.296 | 71 |
| Gerçek strateji alışı / satışı | 1 / 0 | 0 / 0 |
| Olgunlaşmış canlı tahmin sonucu | 0 | 0 |
| Canlı bağımsız dönem / model onay kapısı | 0 / kapalı | 0 / kapalı |

- Dört hesabın nakit, katkı, maliyet, adet ve alacakları `Ledger.account` dışında
  yeniden hesaplandı. Negatif nakit/fazla satış yok; görünümün referans aldığı defter
  kesitiyle değerleme eşleşiyor. BIST stratejisi 1 KCHOL ve 4.791,64 TL nakit;
  altın stratejisi 5.000 TL nakit tutuyor. BIST al-tut hesabının 1,53 TL temettü
  alacağı harcanabilir nakde katılmıyor. Altın al-tut hesabı 0,73 gram ve 49,68 TL.
- Defterdeki bütün dolum fiyatları ve masraflar yürürlükteki hesaplama politikasıyla
  eşleşiyor. Bu, gerçek banka dolumu/ekstresiyle mutabakat yapıldığı anlamına gelmez.
- Eğitim/test sınırlarında sonuç vadesi ayrılmış; kayıtlı modellerde
  `train_label_end < test_start` sağlanıyor. Gerçek SQL'den yeniden eğitimde ağırlık,
  ölçek, eğitim büyüklüğü ve değerlendirme sonuçları 1e-10 mutlak toleransta eşleşti.
  Platformlar arasında yaklaşık 1e-13 düzeyindeki kayan nokta farkı bit eşliği diye
  sunulmadı; kapsüllerin kayıtlı modelle karar tekrarları ise birebir eşleşti.
- Tarihsel modeller de onay almamış: son BIST modelinde 111 bağımsız tarihsel dönem
  ve alt %95 sınır −0,0209 puan; altında 94 dönem ve −2,1668 puan. Sistem bunları
  doğrulanmış üstünlük diye sunmuyor, deneme tutarını sınırlıyor.
- İki gerçek arşivin yedek/geri dönüşünde hash ve dört hesap eşleşti. Her piyasada
  son gerçek fiyatlarla iki tam çevrim, ayrı geçici kökte çalıştırıldı: hesaplar
  değişmedi, ikinci çalıştırma ek alım/katkı üretmedi.

**Kapsam gerçeği:** BIST canlı karar evreni 18 hisse, tarihsel araştırma tabanı 70
hisse. Bu kurulum BIST30'un tamamını işlemiyor. Kapsamı kullanıcının ifadesine uysun
diye değiştirmek yatırım politikasını değiştireceğinden yapılmadı. İlk revizyon
evresindeki 46 defter kararı kapsül mekanizmasından önce; tüm dönem için aynı
güçte kodla tekrar üretim kanıtı varmış gibi sayılmadı.

## Bulunan ve düzeltilen sorunlar

| Şiddet / bulgu | Gerçek kanıt veya tetikleyici | Düzeltme ve regresyon kilidi |
|---|---|---|
| Yüksek — iyileşme bildirimi kayboluyor | BIST 2026-09-22 15:31 TR `ReadTimeout` bildirimi son mesaj olarak kalmış; 17:31 başarılı karar var. Altında da 2026-09-21 referans hatasından dönüş bastırılmış. | `advisor/notifications.py:46,57,87`: günün herhangi bir eski makbuzu yerine son gönderilen durum karşılaştırılıyor. A→hata→A tekrar gönderiliyor; aynı durum tekrarı engelleniyor. `watchdog.py:77` aynı teslim sözleşmesini kullanıyor. |
| Yüksek — eski karar yeni mesaj gibi gönderilebiliyor | Notify komutu görünüm yaşını kontrol etmiyordu; koşu DB/model aşamasında düşerse eski görünümü gönderebilirdi. | Görünüm zamanı tazelik sınırını geçerse gönderim reddediliyor. Hata mesajındaki yanlış “son başarılı kayıt” etiketi düzeltildi. Ağ çağrısının yapılmadığı test ediliyor. |
| Yüksek — altın geçmiş mutabakatı yanlış | 2026-09-21 logunda 398 beklenti, 2026-07-29'un aynı −0,42743 primine bağlanmış. Bağımsız gün eşleştirmesinde yalnız 95 kaydın uygun gerçekleşmesi var; 303 tamamlandı bayrağı geçersiz. Revizyon sonrası 15 beklentinin de doğru gerçekleşmesi yok. | Altın `src/reconcile.py:18,57`: ilk uygun açık günün ilk geçerli kaydı; eski/gelecek/başka haftanın verisi kullanılmıyor. Eksik gün bekliyor. Aynı hatayı tekrarlayan `src/report.py:16` ortak eşleştiriciye bağlandı; eksik beklenti paydadan ayrılıyor. Gerçek DB kopyasında 303 bayrak düzeltildi; ikinci çalıştırma sıfır değişiklik. Üretimdeki eski bayraklar henüz onarılmadı. |
| Yüksek — tekrar içe alma mutabakatı sıfırlıyor | `insert_weekend_exp` her importta `REPLACE` ile tamamlandı bayrağını siliyordu. | Altın `src/db.py:293`: aynı ham girdi bayrağı korur; değişen girdi yeniden değerlendirmeyi gerektirir. Tekrar import ve girdi değişikliği davranış testleri var. |
| Yüksek — veri kaybı paydayı küçültüyor | Canlı sembol listesi fiyat satırlarından türetiliyordu; tüm barları kaybolan hisse kapsamdan da düşüyordu. Yalnız gölge hesapta tutulan, evrenden çıkmış hisse de izlenmeyebilirdi. | `history.py:37`, `service.py:159`: beklenen evren bağımsız tablodan; dört hesabın sahiplik birleşimi korunuyor. Tam çevrim testinde kayıp hisse görünür veri hatası, yalnız gölgede tutulan hissenin stopu çalışıyor. Mevcut gerçek arşivde böyle kayıp hisse görülmedi. |
| Yüksek — belirsiz bölünmede kesin servet | Kurumsal işlem mutabakatı belirsizken güncel fiyat eski adetle çarpılabiliyordu. | `policy.py:40`, `risk.py:5`: değerleme ve kullanılabilir risk bütçesi bilinmiyor olur; son bilinen değer ayrı etiketlidir. Bölünme belirsizliği davranış testi var. Gerçek kesitte hatalı uygulanmış bölünme saptanmadı. |
| Orta — öğrenme vadesi ayarla yeniden yazılabiliyor | Eski tahmin sonuçları güncel ayarın `forward_pct` sütunuyla çözümleniyordu. Vade değişince eski tahminin sınavı değişirdi. | `outcomes.py`, `shadow.py`, `learning.py:134`: tahmin/model vadesi mühürlü; sonuç o vadede hesaplanıyor, farklı vadeler kalibrasyona karışmıyor. Eski V2 kayıtları kendi 20 seans sözleşmesini koruyor. Donmuş model vadesi uyuşmazsa yeni alım engelli, mevcut stop açık. Üretimde henüz sonuç olgunlaşmadığından gerçekleşmiş kirlenme yok. |
| Orta — geçersiz sayıdan görünürde hedef | Altın referansı NaN/inf/negatif olursa zincir bozulabilir; referans yokken “kalan getiri” ham tahmine düşüyordu. Gelecek tarihli analiz de yaş kontrolünden geçiyordu. | `policy.py:73`: sayısal referans/kapanış ve analiz zamanı doğrulanıyor. Gerçek kapsüllerde BIST 72, altın 3 engelli karardaki dayanaksız getiri/hedef gösterimi temizlendi; AL/SAT, dolum ve maliyet değişmedi. |
| Orta — altının Sinyaller bölümü düşüyor | Gerçek logda `NameError: YOK`; FRED rejimi bulunamayınca raporun bütün sinyal bölümü kayboluyordu. | Altın `src/signals.py:200`: eksik rejim açık veri bekliyor sonucuna dönüşüyor, diğer sinyaller korunuyor. Eski kaynakla iki yeni altın regresyon testi kırmızı, yeni kaynakla yeşil. |
| Orta — testler üretim yan etkisine açık | Altında ağ kapatma fixture'ı varsayılan değildi; testler gerçek loga yazıyordu. DB koruması eklenince gerçek DB'yi açan tarih güncelleme testi düştü. | Altın `tests/conftest.py`: ağ ve gerçek DB bağlantısı otomatik engelli; gerçek FileHandler açılmıyor. Hatalı test geçici köke taşındı. Tam paket bu korumalar altında geçti. |
| Orta — analiz gecikmesi sağlıkta görünmüyor | 2026-09-22 altın analizi 2026-09-18; tamamlanmış 2026-09-21 barı eksik. | `service.py:225`, `watchdog.py:64`, panel ve Telegram: beklenen kapanış ve sembol bazlı eksiklik görünür. Kaybolan/kalitesiz veri işlem kapısını kapatır; gecikme için mevcut 5 takvim günü toleransı değiştirilmedi. Gecikmenin üretici nedeni aşağıda açık risk olarak duruyor. |

Yeni ortak testler `tests/test_advisor_production_audit.py`; altın eski hatları için
`tests/test_production_reconciliation.py`. Önce hatayı yeniden üretme, sonra davranış
kilidi ve gerçek arşiv karşılaştırması uygulandı. Ortak motor iki depoda eşlendi.
Hafızadaki “yerel 10 dakika runner çalışıyor” iddiası ölçülen gerçekle değiştirildi;
altın hafızasındaki bozuk ders başlığı ve numara eşliği içerik korunarak onarıldı.

## Açık kalan riskler ve işletim kararı

1. **Yayım bekliyor.** Yerel düzeltmeler üretimi değiştirmedi. Commit/push sonrası
   ilk gerçek çevrimde yeni veri uyarısı, iyileşme makbuzu ve CI görülmeli. Eski altın
   mutabakat bayrakları yeni uzlaştırıcı çalışınca düzelir; geçmişte yazılmış yanlış
   raporlar tarihsel kanıt olarak korunur, geriye dönük başarı gibi düzeltilmez.
2. **Altın günlük üretici ile seans içi tüketici farklı saatte.** Akşam çalışan
   `src/history.py` yarım CME barını doğru biçimde dışlıyor; 2026-09-21 akşam koşusu
   bu yüzden 2026-09-18'de kalmış. Seans öncesi tamamlanmış kapanışı üreten güvenilir
   bir refresh henüz yok. Gün içi banka kotasyonu yeni olsa bile model eski olabilir.
   Uyarı görünür; güncel kapanış varmış gibi varsayılmamalı. Üretici zamanlaması ve
   kaynak erişimi düzelmeden koşulsuz sağlıklı çalışma hükmü verilemez.
3. **Zamanlama yalnız son iki günde güçlü.** 2026-09-16/17/18'de arşivlenmiş seans
   çevrimi günde bir. 2026-09-21/22'de yaklaşık 15 dakika ritim görülüyor; BIST'te
   sırasıyla 30/31, altında 30/30 çevrim. BIST dört fiyat erişim hatasından sonraki
   çevrimde dönmüş. İlgili GitHub çalışmaları `workflow_dispatch`; bu Mac'te kurulu
   advisor LaunchAgent bulunmadı. Haricî tetikleyicinin sürekliliği doğrulanmadı.
   Nöbetçi hâlâ saatlik beklenen slot ve 90 dakika toleransla gözlem yapıyor;
   15 dakikalık hizmet garantisi vermiyor.
4. **Canlı öğrenme sınırı.** Model günlük geçmişle yeniden eğitiliyor; canlı hata
   düzeltmesi henüz başlamadı. 20 seanslık, örtüşmeyen en az 10 dönem kalibrasyon;
   24 dönem canlı kanıt kapısı demek. Bunlar kabaca 200/480 seans ister. Birkaç gün
   çalışmak bu sınavın geçtiğini göstermez. Otomatik model terfisi yok. Gerçek stop,
   satış, zarar dönemi ve aylık katkı henüz canlı yaşanmadı; kontrollü test kanıtı var.
5. **Fiyat ve maliyet temsili.** BIST gecikmeli son fiyat; banka gerçekleşmesi değil.
   Altın banka fiyatı üçüncü taraf sayfadan; tarihsel model vadeli ons×kurdan geliyor.
   Spot/vadeli baz, roll, kur saati ve tarihsel banka makası belirsizlikleri sürüyor.
   Öğrenmenin sonuç etiketi düzeltilmiş toplam getiri serisidir; net banka kârı değildir.
   Hisse temettüsü/makas/vergiyi fiyat hedefiyle birebir eşitlemek bir model varsayımıdır;
   etiket açıklaması bu ayrımı artık açıkça söylüyor. Kişisel tarife/ekstre yok. Saklama ve MKK gibi dönemsel ücretler defterde yok;
   maliyet notlarında artık açık. Resmî [komisyon tarifesi](https://www.isbank.com.tr/komisyon-oranlari)
   işlem komisyonu, asgari tutar/tavan ve BSMV varsayımlarını; [altın hesap koşulları](https://www.isbank.com.tr/vadesiz-altin-hesabi)
   995/1000 banka gramını ve 0,01 gram adımını destekliyor. Altın alış vergisinin
   kişisel uygulanışı bu denetimde ekstreyle doğrulanmadı.
6. **V1 altın ölçüm sorunu devam ediyor.** Bağımsız kabul edilen son prim verisi
   2026-07-29; yakın dönem aynı kaynaktan türeyen ons/gram gerçek bağımsız prim
   ölçmüyor. FRED reel faiz kaynağı sorunlu. Bunlar V2'nin tahmin özellikleri değil,
   fakat eski raporların ilgili sonuçlarına güvenilemez. Veri uydurularak kapatılmadı.
7. **Tarihsel yanlılık ve depolama.** BIST tarihsel üyelik/survivorship belirsizliği
   sürüyor. Kapsüller önceki defteri de taşıyor; veri hacmi büyüdükçe saklama maliyeti
   izlenmeli. Gerçek panelin canlı deployment ve alıcı Telegram ekranı bu kesitte
   bağımsız uç nokta olarak doğrulanamadı.

## Yeniden çalıştırma

Her repo kendi kökünden, `requirements-runtime.txt` ile aynı Python 3.12 ortamında:

```sh
python -m pytest -q
python scripts/advisor_manifest.py --peer '../gold_tracking_system'
cd dashboard
npm test
npm run build
```

Manifest komutundaki peer altın kökünden `../BIST tahmin` olur. Sabit commit'in
ayrı arşiv kopyasına karşı (iki proje için kendi checkout'undan):

```sh
python scripts/audit_production.py --root /tmp/sabit-uretim-kopyasi --output /tmp/denetim.json --replay --validate-fixes
```

Bu komut kod paketlerini kayıtlı runtime ile çalıştırır, güncel motor kararlarını
karşılaştırır, kopyada tam çevrim/yeniden eğitim/yedek dönüşünü sınar. Üretim veri
dizinine rapor yazmayı reddeder. `--replay` eski kodu çalıştırdığı için yalnız kendi
doğrulanmış proje arşivi kullanılmalıdır. Son test sonuçları aynı tarihli
`URETIM-DENETIMI-2026-09-22-dogrulama.json` dosyasındadır.
