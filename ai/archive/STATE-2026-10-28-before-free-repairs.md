# Mevcut durum

**Güncelleme:** 2026-10-28
**Aktif iş:** Tekrarlayan Actions/mail hataları salt-okunur incelendi; rapor hazır,
düzeltmeler kullanıcı onayını bekliyor. Altın çalışıyor; makas engeli veri arızası
diye sınıflanıyor. BIST ödeme/harcama engeliyle durmuş. Ortak deney T0 kapalı; gerçek emir yok.

## 2026-10-01 yeni kapsam ve sınır

- T0 açıldığında beş ayrı sanal kol aynı 50.000 TL + aylık 5.000 TL ile çalışacak; çekirdek
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
- Önceki ölçümler ve yayın öncesi kanıt: `ai/archive/STATE-2026-10-01-prior-work.md`.
- 2026-10-01 üretim Telegram defterinde BIST için 32, altın için 33 başarılı bildirim
  makbuzu var. Vercel paneli HTTP 200, yetkisiz durum API'si HTTP 401 verdi;
  parolalı veri görünümü henüz sınanmadı.
- Eski veri sınavı 2026-10-01'de yeniden koştu: altın raporu birebir aynı;
  BIST'e sonradan eklenen dört test satırı ayrı makbuzda saklandı.
- [Altın canlı koşusu](https://github.com/Mertsaglm/gold_tracking_system/actions/runs/36901918911)
  başarılı; Telegram `message_id: 320`. [BIST koşusu](https://github.com/Mertsaglm/bist-analiz/actions/runs/36901914212)
  başarılı fakat seans dışı atlandı. Vercel'in üç statik dosyası yeni sürümle eş.

## Önceki yerel çalışma

2026-09-25 ve 2026-09-30 kapsamı/kanıtları: `ai/archive/STATE-2026-10-01-prior-work.md`.

## Tamamlananlar

- 2026-10-28: iki deponun 2833 Actions koşusu metadatası, seçili loglar,
  ilgili mailler ve üretim arşivleri incelendi. Altın Ekim'de 57/1000 koşu kırmızı;
  636 kararın 59'u veri bekliyor (57 geniş makas, 2 kaynak yok). Nöbetçi alarmı
  gerçek arşiv kopyasında ağsız tekrarlandı. Kod/veri/ödeme değişmedi.
  Açık bulgular ve kabul ölçütleri: `docs/HATA-DENETIMI-2026-10-28.md`.
- 2026-10-28 ek kontrol: GitHub 23 Ekim'de ücretsiz Actions dakikası, 5 Ekim'de
  depolama hakkının tamamlandığını mail ile bildirdi. Vercel panel yayını READY ve
  ana sayfa 200; usage/log ve parolalı panel yetki nedeniyle doğrulanamadı.
- 2026-10-02 AI talimatları ve devir paketi sadeleştirildi; V1 kapsam/durum
  kesitleri arşivlendi, köprü öncelikleri tekleştirildi. Kritik altın, izolasyon
  ve onay sınırları korundu. Doküman/gizlilik kontrolleri geçti; kod/veri
  eşliği ve arşivlenen metinlerin korunması ayrıca denetlendi. Ayrıntı ADR #026.

## Sıradaki 3 İş

1. Denetim çözüm kapsamını, BIST Billing ve yedek seçeneğini Mert'le kesinleştir.
   DoD: kod, veri onarımı, saklama ve olası maliyet yetkileri açık.
2. Onaylanan makas/veri sınıfları ve kaynak tanısı/retry işlerini iki depoda uygula.
   DoD: geniş makasta alım engeli/koruyucu çıkış korunur; gerçek veri hatası alarm verir.
3. Onaylı yayın sonrası taze çevrim, defter, Telegram ve harici yedek kabulünü yap.
   DoD: atlanmamış üretim, eski defter eşliği; ardından ayrı kararla ortak ileri T0 ve panel.

## TAKVİM

| Tarih | İş | Kim | Durum |
|---|---|:--:|---|
| 2026-09-25 | Yerel düzeltme/eğitim/yeniden sınav | 🤖 | Tamam |
| 2026-09-30 | Üretim sonrası yerel düzeltme ve yayın hazırlığı | 🤖 | Tamam; kod 2026-10-01 yayımlandı |
| 2026-10-01 | Altın ana hesap ve Telegram canlı koşusu | 🤖 | Geçti; deney T0 kapalı |
| 2026-11-25 | GC=F roll etkisi ve bağımsız prim/FRED kapsamı incelemesi | 🤖 | Bekliyor |

## SENDE KALANLAR

- 👤 Üretim yayını 2026-10-01 kullanıcı onayıyla tamamlandı; parolalı Vercel görünümü için kullanıcı oturumu gerekir.
- 2026-10-28: hata raporu için çözüm onayı bekleniyor; ortak T0 henüz açılmadı.

## Backlog / açık dış bağımlılıklar ve sınırlar

- Tarihsel banka kotasyonu/emir sırası, kişisel tarife ve MKK ücretleri.
- Geçmişte bilinen üyelik/fiyat sürümü, temettü ödeme günü, revizyon geçmişli TÜFE.
- Dış 15 dakika tetikleyicisi ve alıcıya Telegram tesliminin bağımsız kanıtı.
- 2027 tahmini takvim kayıtlarını yıl başlamadan resmi kaynakla doğrulama.
- Aday kapsüllerinin büyümesini gözle; geçmiş kanıtı silmeden saklama politikası.
- Önceki arşiv: `ai/archive/STATE-2026-09-25-before-wealth-revision.md`.

- `yeni-proje.sh` ürettiği STATE şablonunda eski sabit görev süresini taşır;
  script kodu bu Markdown revizyonunda değiştirilmedi.
