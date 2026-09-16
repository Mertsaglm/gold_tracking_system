# Mevcut durum

**Güncelleme:** 2026-09-15
**Aktif iş:** BIST + altın revizyonu yerelde doğrulandı. GitHub yayın onayı / Vercel proje kurulumu bekliyor.

## Kullanıcının yeni kapsamı

- İki bağımsız otomatik analiz ve sanal portföy; gerçek emir yok.
- Her hesap için 5.000 TL başlangıç ve aylık 5.000 TL varsayımı.
- İş Bankası fiyat/maliyet referansı, kısa Türkçe kararlar, Telegram + web.
- Geçmiş kararları koru; hataları zaman sıralı ölç, sonuçtan öğren.
- Mevcut GitHub/Vercel ve API anahtarlarını koru.

## Tamamlanan yerel parçalar

- Üretim SQL arşivleri GitHub'dan salt okunur alınıp ayrı geçici DB'de incelendi.
- Telegram export'ları ve proje dosyalarının envanteri çıkarıldı.
- `advisor/`: zincir mühürlü defter, katkılar, tam lot/0,01 gram, maliyet, risk,
  al-tut karşılaştırması, zaman sıralı model ve sonuç günlüğü.
- `dashboard/`: iki hesabı okuyan Birikim paneli, kaynak zamanı, karar araması,
  işlem defteri, öğrenme ve V1 karne ekranları; yerel tarayıcıda açıldı.
- Güncel kamuya açık banka/İş Yatırım referanslarıyla ilk okuma başarılı.
- `portfolio.yml`: tek V2 yazarı; defter GitHub'a kaydolduktan sonra kısa Telegram.
- Push denemeleri tükenirse exit 1; başarısız koşu kurtarma artifact'i.

## Doğrulama tamamlandı — 2026-09-15

- Tam suite: 919 test geçti; 7 eski CLI modül kontrolü, CLI girişi olmadığı için atlandı.
- Son etiket/gün düzeltmesi sonrası V2 davranış testleri: 39 geçti; API: 4 geçti.
- Node build, git diff --check, yeni/değişen dosyalarda mevcut anahtar değeri taraması geçti.
- Üretim SQL restore, güncel fiyatlı tekrar koşu, aylık katkı/çift işlem koruması doğrulandı.
- Web masaüstü + 390×844 mobil: piyasa/arama/filtre/karne/portföy; yatay taşma yok.
- Rehber: `docs/V2-REHBER.md`; rapor: `reports/REVIZYON-2026-09-15.md`.
- Commit, push, merge, production deploy veya gerçek Telegram denemesi yapılmadı.

## Bağlantılar / kısıtlar

- GitHub iki depoyu okuyor. BIST PR #1 açık; önceden bekleyen değişiklikler korunuyor.
- Vercel tarayıcı oturumu açıldı: mert-saglams-projects ekibine erişim var.
  Görünen projelerde BIST/altın yok; ortak panel projesi kurulacak. Eski CLI tokenı 403.
  Import aramasında BIST bulunmuyor; Vercel, GitHub App depo erişimi istiyor.
- BIST referansı gecikmeli son fiyat; emir defteri yok. Altın fiyatı bankaya özgü
  ikincil kaynak; İşCep kişisel kotasyonu değil. Bunlar panelde açıkça yazıyor.
- Tarihsel banka makası yok; yeni modelin geçmiş testi tam portföy testi değildir.
- Temettü ödeme tarihi kaynağı yok; alacak ayrı izlenir, harcanabilir nakit olmaz.

## Sıradaki 3 İş

1. Hazır revizyon paketinin GitHub yayın onayını alıp iki depoya gönder; BIST PR #1'i
   son içerikle birleştir. DoD: onaylı commit'ler main'de, ilk V2 Actions koşusu doğrulandı.
2. Vercel oturumunu/proje hedefini doğrula; dashboard kökü, sunucu GitHub okuma tokenı
   ve panel parolasıyla preview çıkar. DoD: iki hesap aynı panelde, anahtar tarayıcıda yok.
3. Onaylanan paneli production'a al, dashboard_url ve Telegram teslimini doğrula.
   DoD: gerçek panel adresi ve kısa mesajdaki kayıt aynı defter/hash ile eşleşiyor.

## Korunan geçmiş / araştırma

Önceki durum ve karar bekleyen ayrıntılar:
`ai/archive/STATE-2026-09-before-revision.md`.
Eski taktik/prim kuralları geçmiş arşivin parçasıdır; V2 kararını yönetmez.
Eski kararlar geriye dönük başarı gibi yeniden yazılmayacak.

## TAKVİM & SENDE KALANLAR

| Ne zaman | Kim | İş | DoD | Durum |
|---|---|---|---|---|
| 2026-09-15 | 🤖 | Revizyon doğrulaması | Test + panel + rehber tamam | Tamam |
| Yayın paketi hazır olduğunda | 👤 | Commit/push ve yayın kararı | Somut paket onaylandı | Bekliyor |
| 2026-11-25 | 🤖 | Altın vadeli referansta roll etkisini kontrol et | Kaynak farkı ayrı raporlandı | Bekliyor |

## Backlog

- Doğrudan İş Bankası yetkili fiyat API'si ve kişisel komisyon tarifesi.
- Temettü ödeme tarihini doğrulayan kaynak; alacağın nakde mutabakatı.
- Yeni sanal sonuçlar birikince bağımsız dönemli üstünlük testi.
