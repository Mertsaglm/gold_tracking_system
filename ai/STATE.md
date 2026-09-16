# Mevcut durum

**Güncelleme:** 2026-09-16
**Aktif iş:** Üç öncelik grubu yerelde uygulandı ve doğrulandı; GitHub yayın ve CI takibi sürüyor.

## Kapsam

- BIST + altın: iki ayrı sanal hesap, 5.000 TL başlangıç/aylık katkı varsayımı.
- Kullanıcı 25 öneriden ilk üç öncelik grubunun uygulanmasını istedi.
- Dağılım 8 + 7 + 7 + 3; ilk 22 madde uygulandı, son üç madde ertelendi.
- Önceki 25/26 sürüm-doküman maddeleri birleştirildi. Gerçek emir yok.

## Tamamlandı — 2026-09-16

- Eski analiz mevcut stopu kapatmaz; eski fiyat güncel değerleme/bütçe üretmez.
- Ortak tam/yarım gün takvimi, seans vadesi, al-tut nakit cepleri, toplam risk.
- Ayrı V2 nöbetçisi ve yedek/geri dönüş workflow'ları; panel Node CI.
- Tam sanal portföy geçmiş motoru, maliyet/boşluk/aksama stresleri.
- Bağımsız dönem kanıtı; sabit/günlük model için ayrı gölge hesaplar.
- Tarihli evren, kanıtlı temettü ödeme ve masraf gözlemi içe alma araçları.
- Karar detay/değişim/dağılımı, haftalık sonuç, mühürlü karar yeniden üretimi.
- Ortak kod manifesti, runtime kilitleri, rehber ve işletim dokümanları.
- Toplu plan: `docs/IYILESTIRME-2026-09-16.md`.
- Kanıt/sınırlar: `reports/IYILESTIRME-2026-09-16.md`; kullanım: `docs/V2-REHBER.md`.

## Doğrulama

- Tam suite: BIST 1.393 geçti; altın 944 geçti, 7 eski CLI testi atlandı (2026-09-16).
- İki panelde npm test/build geçti; masaüstü ve 390×844 mobil kontrolü başarılı.
- İki projede 27 ortak modül eşleşiyor; pip check ve git diff --check geçti.
- Eski stop hatası geçici kopyada geri konunca regresyon testi kırmızıya döndü.
- Gerçek defterlerin ayrı arşivden geçici geri dönüşünde tüm hesap/hash eşleşti.
- Başlangıçtaki 19 veri dosyasının SHA-256 özeti değişmedi; gizli değer sızıntısı yok.
- Bu oturum iki depoya commit/push yaptı; gerçek Telegram gönderimi veya deploy yapılmadı.

## Açık sınırlar

- 2026-06-01–2026-08-26 yerel tarihsel denemelerinde strateji işlemi yok.
  Kârlılık kanıtı yok; işlemli mekanizma senaryoları kontrollü testlerde doğrulandı.
- Tarihsel banka makası, kişisel masraf ve ödeme belgeleri henüz sağlanmadı.
- Tarihsel evren kaynağı yok; güncel evren varsayımı açıkça etiketleniyor.
- Bağımsız sanal dönem birikimi zaman ister; otomatik model terfisi yok.
- Altın eski .venv pandas 3 içeriyor; kilit pandas 2.3.3/tzdata 2026.3.
  Test geçici PYTHONPATH ortamında yapıldı; eski .venv değiştirilmedi.
- Vercel hesabı canlı incelendi; BIST/altın paneline bağlı proje görünmüyor.

## Sıradaki 3 İş

1. BIST `main`deki ilk yeni V2 koşusu ile nöbetçi/yedek işlerini izle.
   DoD: yeni defter yazımı, nöbetçi ve geri dönüş artifact'i ayrı ayrı yeşil.
2. Vercel'de panel için proje/GitHub erişimi kur, preview'a yalnız sunucu değişkenlerini ekle.
   DoD: iki gerçek hesapta güncel tarih/hash, korunmuş sunucu anahtarı, teslim makbuzu.
3. Doğrulanmış üyelik/ödeme/masraf kaynaklarını edin ve yeni sanal kanıtı biriktir.
   DoD: belgeli kayıtlar idempotent içe alındı; boşluklar ve bağımsız dönem sayısı görünür.

## TAKVİM & SENDE KALANLAR

| Tarih | Kim | İş | DoD | Durum |
|---|---|---|---|---|
| 2026-09-16 | 🤖 | BIST PR #2 squash merge edildi | `34273ab`, GitHub dashboard + pytest yeşil | Tamam |
| 2026-09-16 | 🤖 | Altın `main` yayımlandı | GitHub dashboard + pytest yeşil | Tamam |
| Vercel kurulumunda | 👤 | Panel projesine GitHub erişimi ver | Preview kurulabilir | Bekliyor |
| Veri bulunduğunda | 👤 | Üyelik/ödeme/masraf kanıtı sağla | Belgeli içe alma kaydı | Bekliyor |

## Backlog

- Grup 4: panelden ayar, gerçek işlem günlüğü, etkileşimli senaryo ekranı.
- Bankanın yetkili fiyat kaynağı ve kişisel tarife doğrulaması.
- 2026-11-25: altın GC=F referansında roll etkisini ayrı ölç.
- Önceki ayrıntılar: `ai/archive/STATE-2026-09-16-before-improvements.md`.
- V1 geçmiş araştırma ve ölçümleri korunur; V2 başarısı gibi yeniden yazılmaz.
