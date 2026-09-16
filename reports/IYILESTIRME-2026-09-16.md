# Üç öncelik grubunun uygulama raporu — 2026-09-16

## Sonuç ve kapsam

25 öneri **8 / 7 / 7 / 3** olarak gruplandı. İlk üç gruptaki 22 maddenin yerel
uygulaması tamamlandı. Önceki fikir listesindeki 25 ve 26 numaralı sürüm/doküman
bakımı tek madde sayıldı. [Madde eşleştirmesi ve bitti tanımları](../docs/IYILESTIRME-2026-09-16.md).

BIST ve altın ayrı hesaplarını korur. Mevcut SQL/DB ve advisor hesap dosyaları
bu çalışmada değiştirilmedi. Yeni davranışlar ilk yeni koşuda devreye girer;
önceki sonuçların başarısı geriye dönük değiştirilmez. Değişiklikler yereldedir;
GitHub Actions, Telegram teslimi ve Vercel yayını bu raporla doğrulanmış sayılmaz.

## Grup 1 — Yanlış hesap ve sessiz durmayı önleme (8)

| İş | Uygulanan davranış / yarar |
|---|---|
| Stop kontrolü | Eski analiz, geçerli fiyatla mevcut stop/hedef/süre çıkışını kapatmaz. Korumasız bekleme önlenir. |
| Bayat değerleme | Eski fiyat son bilinen değer olarak ayrılır; kâr ve yeni alım bütçesi oluşturmaz. |
| Takvim | Tam/yarım günler YAML alanlarından okunur; vade seansla ilerler. Yanlış tatil/son gün hesabı azalır. |
| Nöbetçi | Ayrı salt-okur iş kaçırılan seansı, başarısız koşuyu, fiyat eksiğini ve makbuzu kontrol eder. Gece koşusu gündüz eksikliğini gizleyemez. |
| Al-tut nakdi | Bir eksik fiyat diğer hisseyi durdurmaz; lot artığı sonraki katkıyla birleşir. Karşılaştırma nakdi gereksiz kilitlemez. |
| Panel CI | Test/build workflow'a bağlandı. Bozuk hesap içeriği sağlıklı hesabı gizleyemez. |
| Toplam risk | Portföy stop riski yeni işlem tavanıyla sınanır; ortak düşüş senaryoları görünür. Ayrı küçük risklerin büyük toplam oluşturması engellenir. |
| Kurtarma | Checksum arşivi boş geçici dizine geri yüklenip hesap/hash doğrulanır. Yedek dosyasının açılabilir olduğu ölçülür. |

## Grup 2 — Sonucu dürüstçe ölçme (7)

| İş | Uygulanan davranış / yarar |
|---|---|
| Tam portföy deneyi | Ortak karar ve muhasebe motoruyla katkı, lot, nakit, maliyet ve çıkışlar işlenir. Tahmin doğruluğu ile para sonucu karıştırılmaz. |
| Gerçekleşme stresi | Fiyat boşluğu, satılamama, bayat fiyat, atlanan kontrol ve maliyet katı denenebilir. İyimser dolum varsayımı görünür olur. |
| Masraf/kotasyon kaydı | Kotasyonlar ve maliyet ayar sürümü mühürlenir; belgeli gözlem farkları içe alınabilir. Kişisel tarife doğrulanmış gibi gösterilmez. |
| Temettü ödemesi | Kaynak referanslı ödeme alacağı yalnız bir kez nakde çevirir. Aynı temettünün ikinci kez kâr yazılması engellenir. |
| Bağımsız kanıt | Örtüşmeyen dönem ve güven alt sınırı yeni risk bütçesini yönetir. Aynı piyasa hareketi çok sayıda başarı sayılmaz. |
| Model kıyası | Sabit önceki ve günlük model, eşit başlangıçlı ayrı gölge hesaplarda izlenir; tahmin hatası ayrıca ölçülür. Otomatik terfi yoktur. |
| Tarihsel evren | O gün bilinen üyelikleri doğrulayan içe alma ve seçim mekanizması kuruldu. Günümüz kazananlarının geçmişe taşınması açıkça etiketlenir. |

## Grup 3 — Anlama ve bakım (7)

| İş | Uygulanan davranış / yarar |
|---|---|
| Karar detayı | Miktar, tutar, masraf, stop ve hedef sonucu görünür. Kararın hesapla bağlantısı izlenebilir. |
| Ne değişti? | Önceki fiyat, gerekçe, eylem ve model sürümüyle fark gösterilir. Tekrarlanan mesajın anlamı anlaşılır. |
| Bekleme dağılımı | Veri, model, fırsat ve bütçe/risk nedenleri tam paydasıyla sayılır. Sistem neden işlem açmıyor sorusu yanıtlanır. |
| Haftalık özet | Eklenen para, yatırım sonucu, masraf ve al-tut farkı ayrı raporlanır. Katkı kâr sanılmaz. |
| Ortak kod eşliği | İki projede advisor manifesti ve sapma testi var. Tek kopyayı düzeltip diğerini unutmak yakalanır. |
| Yeniden üretim | Girdi, kod, model, ayar ve bağımlılık sürümlü karar kapsülü tekrar çalıştırılabilir. Eski karar sonradan denetlenebilir. |
| Sürüm/doküman bakımı | Runtime kilitleri, CI, rehber, ADR, dersler ve kısa STATE güncellendi. Yeni kurulumun sessizce farklılaşması azaltılır. |

## Grup 4 — Ertelenenler (3)

Panelden ayar değiştirme, gerçek işlem günlüğü ve etkileşimli senaryo ekranı
uygulanmadı. Araştırma için komut satırı simülasyonu Grup 2 kapsamındadır;
Grup 4'teki ek kullanıcı arayüzüyle aynı iş değildir.

## Doğrulama — 2026-09-16

- Python tam suite: BIST **1.393 geçti**; altın **944 geçti, 7 atlandı**.
  Ölçüm tarihi 2026-09-16. Altında mevcut CLI girişi olmayan yedi test atlanır;
  yeni testlerin atlaması değildir.
- Her panel kopyasında `npm test`: 7 geçti; `npm run build`: geçti.
- Ortak 27 Python modülü manifest ve iki gerçek proje karşılaştırmasıyla eşleşti.
- Canlı kaynaklar taklit edilerek geçici hesapta tam cycle, defter, panel çıktısı ve
  arşivlenmiş kodla karar tekrar üretimi iki piyasada başarılı oldu.
- Mobil 390×844 ve masaüstü panel kontrolü: karar detayı, risk/haftalık özet,
  bağımsız kanıt ve iki gölge hesap görünür; yatay taşma yok, konsol hata/uyarı yok.
- Stop hatası yalnız geçici kaynak kopyasında geri konuldu: ilgili regresyon testi
  SAT beklerken VERİ BEKLENİYOR alarak kırmızıya döndü. Test eski hatayı yakalıyor.
- İki gerçek mevcut defterin yedeği ayrı /tmp arşivlerinden geçici dizine geri
  yüklendi; checksum ve hesap tutarlılığı doğrulandı. Asıl dosyalara yazılmadı.
- Başlangıçta kaydedilen 19 SQL/DB/defter/görünüm dosyasının SHA-256 özeti aynı kaldı.
- `pip check`: BIST geçti. Altında kilitteki pandas 2.3.3 + tzdata 2026.3 geçici
  Python yoluna alınarak geçti; kullanıcının mevcut .venv'i değiştirilmedi.
- Mevcut .env gizli değerleri yeni/değişen dosyalarda bulunmadı.
- `git diff --check` iki projede geçti. Bu çalışma commit/push/deploy yapmadı;
  mevcut `effc191` tabanı bu çalışmadan öncedir. Gerçek Telegram gönderilmedi.

## Tarihsel deneme: ne öğrendik?

Yerel SQL, 2026-06-01–2026-08-26 aralığında salt okunur açıldı. BIST yerel
arşivinin son barı 2026-08-26; bu deneme güncel production veri iddiası değildir.

BIST temel denemede 18 veri engeli, 699 fırsat yokluğu, 399 getiri/risk eşiği
nedeniyle **0 strateji işlemi** üretti; al-tut 51 işlem yaptı. Altında son temel
deneme 1 veri engeli, 58 fırsat yokluğu, 1 getiri/risk eşiğiyle **0 strateji
işlemi** üretti; al-tut aylık alımlar yaptı. Her iki piyasada iki kat maliyet ve
her üçüncü kontrolü atlama senaryosu da tamamlandı.

İlk altın denemesi tam %3 makası float yuvarlama nedeniyle sınır üstünde
sayıyordu. Ondalık karşılaştırma ve sayısal toleransla düzeltildi; tam sınır,
hesaplanmış ondalık fiyat ve gerçek sınır aşımı testleri eklendi.

**Bu sonuç kârlılık kanıtı değildir.** Eşikler sırf işlem üretmek için gevşetilmedi.
İşlemli nakit/stop/boşluk/maliyet senaryoları kontrollü testlerde doğrulandı;
gerçek tarihsel aralıkta sıfır işlem varken bunların getiriyi iyileştirdiği ileri sürülemez.

## Açık veri ve işletim sınırları

- Tarihsel banka makası ve kişisel masraf belgeleri elde yok; varsayım ve kaynak
  farkı korunur. İçe alma araçlarının hazır olması gerçek verinin varlığı değildir.
- Tarihsel üyelik kaynağı henüz içe alınmadı. Güncel evrenle simülasyonun yanlılığı
  etiketlenir. Sonradan düzeltilmiş OHLC, gerçek eski lot/nakit akışının tamamı değildir.
- Doğrulanmış temettü ödeme tarihleri henüz alınmadı; mevcut alacaklar harcanabilir
  para yapılmadı. Otomatik banka/ekstre bağlantısı eklenmedi.
- Yeterli yeni bağımsız dönem birikmedi; üstünlük kapısı kapalı kalabilir.
- Güncel bulut çalışma kopyası, Actions zamanlama/retention ve gerçek mesaj teslimi
  yayın sonrası ayrıca doğrulanmalıdır. Kullanım: [V2 rehberi](../docs/V2-REHBER.md).

## Tekrar kontrol

Her projenin kendi Python 3.12 ortamında kilitli bağımlılıkları kurduktan sonra:

```bash
python -m pytest -q
python scripts/advisor_manifest.py
npm --prefix dashboard test
npm --prefix dashboard run build
python -m advisor simulate --start 2026-06-01 --end 2026-08-26 --output /tmp/portfoy-tekrar.json
```

Simülasyon çıktısı yeni bir geçici dosyadır. Gerçek hesapta deneme amaçlı `cycle`
koşmak yerine `tests/test_advisor_flow.py` ve ölçüm testlerinin geçici hesaplarını kullan.
