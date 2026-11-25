# Mevcut durum

**Güncelleme:** 2026-10-29
**Aktif iş:** Kodlar iki uzak main'e yayımlandı; Gold CI ve gerçek operasyon
  yedeği/geri dönüşü geçti, Vercel production READY. Mert iki somut iş için
  “sen tercih et” yetkisi verdi: TMSN tek bar onarımı üretime uygulandı;
  12 eski BIST artifact silindi, son bulut yedeği ve 13 yerel kopya korundu.
  BIST runner öncesi ödeme/harcama engeli sürüyor. Ücretli servis/limit açılmadı.
  Piyasa açık taze çevrim kabulü ve ortak deney T0 henüz yok.

## 2026-10-01 yeni kapsam ve sınır

- Beş sanal kol, bütçe/muhasebe, model sınavları, önceki SQL provaları ve
  2026-10-01 canlı makbuzların tam kesiti yayın sonrası arşivde korunur.
  `experiment_start_date` null; yeni ortak T0 açılmadı, otomatik terfi yok.

## Önceki yerel çalışma

2026-09-25 ve 2026-09-30 kapsamı/kanıtları: `ai/archive/STATE-2026-10-01-prior-work.md`.

## Tamamlananlar

- 2026-10-29 eski girdisiz dispatch gerçek GitHub koşusunda runner almadan
  atlandı (40899224420); fiyat/defter adımı çalışmadı, makbuz raporda.

- 2026-10-29: TMSN kaynakla doğrulanan düşük fiyatı 50,00'a onarıldı
  (`4101882`); tek SQL satırı/düşük+ingestion değişti, dört mevcut
  OHLC testi geçti ve uzak blob test edilen SQL ile eşleşti. Eski karar/defter aynı.
  12 eski artifact 933.906.756 byte temizlendi; 336.038.973 byte son bulut yedeği
  ve 13 doğrulanmış yerel kopya korundu. Somut iki soruya “sen tercih et” yetkisi.

- 2026-10-29 yayın: `9829c43`; Gold GitHub CI geçti.
  `reports/duzeltmeler-2026-10-29/publication.json` güncel makbuzdur.
  Yerel kirli çalışma ağacı/branch reset veya rebase edilmedi; önceden değişmiş
  belgeler yayına katılmadı. Sonraki yayında eski yerel SQL kullanılmamalı.

- 2026-10-29: tam suite 1026 geçti/9 atlandı; son hedef küme 56 geçti.
  Makbuz: `reports/duzeltmeler-2026-10-29/validation.json`.
- 2026-10-29: makas/veri ayrımı, güvenli kaynak tanısı/sınırlı retry, ortak parçalı
  v2 kapsül ve kapsamı etiketli operasyon yedeği iki depoda yerel olarak tamamlandı.
  BIST saatlik ve eski girdisiz dış dispatch kapalı; V1 LLM kapalı, veri nöbeti açık.
  BIST OHLC ve V1/V2 yarım gün kapanış simetrisi düzeltildi. Gold ritmi korunur.
  %3 eşik, stop, eski defter/kanıt ve üretim SQL'si korunur. Ayrıntı/kanıt sınırları:
  `docs/DUZELTMELER-2026-10-29.md`; ADR #027.

- 2026-10-28 Actions/mail denetimi ve tarihli kota kanıtı
  `docs/HATA-DENETIMI-2026-10-28.md` ve önceki durum arşivindedir.
- 2026-10-02 AI talimatları ve devir paketi sadeleştirildi; V1 kapsam/durum
  kesitleri arşivlendi, köprü öncelikleri tekleştirildi. Kritik altın, izolasyon
  ve onay sınırları korundu. Doküman/gizlilik kontrolleri geçti; kod/veri
  eşliği ve arşivlenen metinlerin korunması ayrıca denetlendi. Ayrıntı ADR #026.

## Sıradaki 3 İş

1. GitHub ücretsiz hak/ödeme engeli kalkınca BIST'in gerçek taze çevrimini kabul et.
   DoD: runner başlamış, beklenen kapanış/evren tamam, eski defter eş ve Telegram
   makbuzu var. Temizlik dakika iade etmez; ücret/harcama limiti artırılmaz.
2. Yeni BIST operasyon yedeğini gerçek runner'da oluşturup geri dönüşünü doğrula.
   DoD: kapsam etiketli küçük artifact, muhasebe eşliği ve ücretsiz bütçe ölçümü;
   mevcut 336 MB bulut yedeği kabul kanıtı çıkmadan ayrıca silinmez.
3. Piyasa açık yeni kodla iki piyasa kabulünden sonra ortak ileri T0'ı ayrı değerlendir.
   DoD: taze veri ve bağımsız hesap/masraf eşliği; otomatik T0/aday terfisi yok.

## TAKVİM

| Tarih | İş | Kim | Durum |
|---|---|:--:|---|
| 2026-09-25 | Yerel düzeltme/eğitim/yeniden sınav | 🤖 | Tamam |
| 2026-09-30 | Üretim sonrası yerel düzeltme ve yayın hazırlığı | 🤖 | Tamam; kod 2026-10-01 yayımlandı |
| 2026-10-01 | Altın ana hesap ve Telegram canlı koşusu | 🤖 | Geçti; deney T0 kapalı |
| 2026-11-25 | GC=F roll etkisi ve bağımsız prim/FRED kapsamı incelemesi | 🤖 | Bekliyor |

## SENDE KALANLAR

- 👤 Üretim yayını 2026-10-01 kullanıcı onayıyla tamamlandı; parolalı Vercel görünümü için kullanıcı oturumu gerekir.
- 2026-10-29: kod ve onaylı veri/yedek işlemleri yayımlandı; BIST kota engeli
  ve piyasa açık kabulü sürüyor, ortak T0 açılmadı.

## Backlog / açık dış bağımlılıklar ve sınırlar

- Tarihsel banka kotasyonu/emir sırası, kişisel tarife ve MKK ücretleri.
- Geçmişte bilinen üyelik/fiyat sürümü, temettü ödeme günü, revizyon geçmişli TÜFE.
- Dış 15 dakika tetikleyicisi ve alıcıya Telegram tesliminin bağımsız kanıtı.
- 2027 tahmini takvim kayıtlarını yıl başlamadan resmi kaynakla doğrulama.
- Aday kapsüllerinin büyümesini gözle; geçmiş kanıtı silmeden saklama politikası.
- Önceki arşiv: `ai/archive/STATE-2026-09-25-before-wealth-revision.md`.

- `yeni-proje.sh` ürettiği STATE şablonunda eski sabit görev süresini taşır;
  script kodu bu Markdown revizyonunda değiştirilmedi.

Önceki durumun tam kesiti: `ai/archive/STATE-2026-10-28-before-free-repairs.md`.

Yayın sonrası tam kesit: `ai/archive/STATE-2026-10-29-after-publication.md`.
