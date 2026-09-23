# Mevcut durum

**Güncelleme:** 2026-09-23
**Aktif iş:** Vercel paneli yayında; yerel denetim düzeltmeleri iki depoda GitHub üretim arşiviyle birleştirilip yayımlanıyor.

## Kapsam ve doğrulanmış gerçek

- BIST ve banka gram altını ayrı sanal hesaplar; gerçek emir gönderimi yok.
- 2026-09-15–2026-09-22 üretimi sabit GitHub commit arşivlerinden incelendi.
- BIST canlı evreni 18 hisse; BIST30'un tamamı değil. Araştırma tabanı 70 hisse.
- 143 mühürlü karar paketi kendi kod/runtime'ıyla birebir yeniden üretildi.
- Dört hesabın muhasebesi bağımsız hesapla, yedek dönüşü ve tekrar çevrimiyle sınandı.
- BIST stratejide 1 alış, 0 satış; altında 0 işlem. Canlı tahmin sonucu henüz yok.
- Model onayları kapalı, canlı kalibrasyon düzeltmesi sıfır; üstünlük kanıtı yok.

## Tamamlandı — 2026-09-22, henüz yayımlanmadı

- Telegram A→hata→A iyileşmesi, eski görünümü gönderme ve nöbetçi makbuz kontrolü.
- Eksik hisse geçmişinin paydayı daraltması; yalnız gölge hesaptaki stop takibi.
- Belirsiz kurumsal işlemde kesin servet/risk bütçesi göstermeme.
- Model/tahmin vadesini mühürleme; farklı vadeli sonuçları kalibrasyonda ayırma.
- Geçersiz fiyat/referans ve gelecekteki analiz; dayanaksız hedef/getiri temizliği.
- Geciken analiz panel/Telegram/nöbetçide görünür; fiyat korumaları değişmedi.
- Altın eski hattında yanlış gün mutabakatı, importta bayrak sıfırlama ve YOK hatası.
- Altın testlerinde otomatik ağ/üretim DB/log koruması; sızan test izole edildi.
- Ortak motor iki depoda eş; regresyon testleri ve gerçek veri karşılaştırması hazır.
- Kanıt: `reports/URETIM-DENETIMI-2026-09-22.md` ve aynı adlı JSON ekleri.
- Komut: `python scripts/audit_production.py --root /tmp/sabit-kopya --output /tmp/denetim.json --replay --validate-fixes`.
- Üretim defteri/SQL değiştirilmedi; gerçek Telegram mesajı, commit/push/deploy yapılmadı.

## Açık sınırlar

- 2026-09-23'te altın SQL'i 2026-09-21 kapanışındaydı; yerel düzeltme seans öncesi
  tamamlanmış barı geçici DB'de doğrulayıp atomik yayımlar. Eski kapanış yeni alımı kapatır;
  mevcut stop açık kalır. Gerçek GC=F ile 2026-09-22 barı izole kopyada üretildi.
- İki portföy workflow'una 30 dakika nominal GitHub cron yedeği, nöbetçiye 45 dakika
  çevrim boşluğu gözlemi eklendi. Üretimde henüz yayımlanmadı; GitHub zaman garantisi yok.
- Eski altın mutabakatının 303 yanlış tamamlandı bayrağı kopyada düzeltildi.
  Üretimde yeni uzlaştırıcı çalışana kadar eski bayraklar ve eski raporlar geçersizdir.
- 2026-09-16/17/18'de günde bir seans çevrimi; 2026-09-21/22'de yaklaşık 15 dakika.
  GitHub gerçek tetik türü workflow_dispatch. Bu Mac'te kurulu advisor LaunchAgent yok.
  Eski hafızanın yerel 10 dakika runner iddiası doğrulanmadı; haricî çağıranın güvencesi bilinmiyor.
- Haricî 15 dakika dispatch çağırıcısının kimliği hâlâ doğrulanmadı; yedek bunu bağımlılık
  olmaktan çıkarır fakat 15 dakika SLA'sı vermez.
- Telegram dışa aktarımları revizyon sonrasını kapsamıyor; alıcı ekranı doğrulanamadı.
- Gerçek satış/stop/aylık katkı henüz yaşanmadı; yalnız kontrollü test kanıtı var.
- Altın bağımsız prim ve FRED kaynak sorunları sürüyor; eski rapor V2 öğrenme kanıtı değil.
- Kişisel tarife/ödeme belgesi, tarihsel banka makası ve BIST tarihsel üyelik verisi yok.
- Saklama/MKK dönemsel ücretleri sanal defterde yok; maliyet notunda açık.
- Panel 2026-09-23'te `https://birikim-paneli.vercel.app/` adresinde iki sanal hesabı gösterdi; parolasız API isteği 401 döndü. Yeni kodla yeniden yayın ve ilk üretim çevrimi henüz doğrulanmadı.

## Sıradaki 3 İş

1. İki depodaki düzeltmeleri yayımla; son üretim arşivini koruyarak birleştir.
   DoD: CI yeşil, gerçek çevrim yeni uyarı ve izlenebilir makbuz üretiyor; hesap mutabakatı aynı.
2. İlk üretim seansında yedek cron, altın refresh ve 45 dakika nöbetçi bulgusunu doğrula.
   DoD: beklenen kapanış arşivde; eksikse alım yok; kaçan çevrim nöbetçide görünür.
3. Güncel Telegram alıcı kaydını arşiv/makbuzla ve ilk olgunlaşan sonucu karar kapsülüyle eşleştir.
   DoD: teslim zinciri, mühürlü vade ve sonuç hesabı gerçek veriden yeniden üretilebilir.

## TAKVİM & SENDE KALANLAR

| Tarih | Kim | İş | DoD | Durum |
|---|---|---|---|---|
| 2026-09-22 | 🤖 | Üretim denetimi ve yerel düzeltme | Test ve gerçek arşiv kanıtı | Tamam |
| 2026-09-23 | 🤖 | Yerel düzeltmelerin commit/push/yayını | Doğrulanmış dosyalar üretime taşınır | Devam ediyor |
| 2026-09-23 | 👤 | Panel projesine GitHub erişimi | Canlı panelde iki hesap görünür | Tamam |
| Veri bulunduğunda | 👤 | Üyelik/ödeme/masraf kanıtı | Belgeli içe alma/mutabakat | Bekliyor |

## Backlog

- Kapsül büyümesini ve arşiv saklama maliyetini izle; geçmiş karar kanıtını kaybetme.
- Grup 4: panelden ayar, gerçek işlem günlüğü, etkileşimli senaryo ekranı.
- 2026-11-25: altın GC=F referansında roll etkisini ayrıca ölç.
- Önceki durumun tam kopyası: `ai/archive/STATE-2026-09-22-before-production-audit.md`.
- 2026-09-23 açık risk aksiyonu: `reports/ACIK-RISKLER-2026-09-23.md`.
- Ayrıntılı eski çalışmalar: `docs/IYILESTIRME-2026-09-16.md`; V1 ölçümleri korunur.
