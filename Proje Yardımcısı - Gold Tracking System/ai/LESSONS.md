# LESSONS.md — Dersler ve Anti-Pattern'ler

> Geçmiş hatalardan çıkan dersler. Usta bunları bilir ve aynı çukura ikinci
> kez düşülmesine izin vermez. `/ders <olay>` komutuyla yeni ders eklenir.
> Bu dosya projeler arası taşınır — dersler birikir.
>
> ⚠️ **NUMARA UZAYI ORTAKTIR.** Bu dosya ile projenin kökündeki `ai/LESSONS.md`
> **aynı L-NNN numaralarını paylaşır**; buradaki sürüm genelleştirilmiş,
> oradaki proje ayrıntılıdır. Yeni ders eklerken **iki dosyadaki en büyük
> numaraya** bak (bkz. `DECISIONS.md` #003).

---

## L-015 — Test yazmak yetmez: testin DÜŞEBİLDİĞİNİ kanıtla

**Olay:** Bir projeye yüzlerce koruma testi yazıldı ve hepsi ilk koşumda yeşil
geçti. Bu tek başına hiçbir şey kanıtlamıyordu — L-012 zaten "yeşil kalarak
yanlış güven veren test" vakasıydı. Bu yüzden korumalar tek tek, kontrollü
biçimde **bozuldu** (mutasyon): bir filtre gevşetildi, bir eşik koda gömüldü,
bir fonksiyonun parametre sırası değiştirildi, bir tablo kalıcılık listesinden
düşürüldü... Her mutasyon `try/finally` ile geri alındı ve hepsinin
yakalandığı görüldü. Ancak bundan sonra "bu testler koruyor" cümlesi ölçüme
dayandı.

**Ders:** Bir testin değeri geçmesinde değil, **doğru durumda düşmesinde**dir.
"Testi yazdım, geçiyor" ölçüm değil temennidir.

**Kural:** Kritik bir koruma testi yazdığında korumayı bilerek boz, testin
düştüğünü gör, geri al. Düşmüyorsa test yanlış şeyi ölçüyordur. Toplu mutasyon
koşumundan sonra çalışma alanının temiz kaldığını (`git status`) da doğrula.

---

## L-014 — Korumanın KAPSAMI da denetlenir: kilidi takıp kapıyı açık bırakma

**Olay:** "Bu kayıt değiştirilemez" garantisi bir veritabanı trigger'ıyla
kuruluydu ve gerçekten çalışıyordu — ama yalnız **UPDATE** için; **DELETE**
tamamen serbestti. Oysa kaydı güzelleştirmenin en kısa yolu düzeltmek değil
silmekti. Ayrıca trigger'ın koruduğu kolon listesinde, kaydın **hangi kümeye
sayıldığını** belirleyen iki kolon eksikti; tek satırlık bir UPDATE ile bir
kayıt başka bir kümeye taşınabiliyordu.

**Ders:** L-011 "koruma bağlanmamış" diyordu; bu onun kardeşi: koruma **bağlı
ama kapsamı eksik**. Kısmi koruma, tam koruma sanıldığı için daha tehlikelidir.

**Kural:** Koruma yazınca üç soruyu sor: (1) hangi **fiiller** kapalı
(oluşturma/değiştirme/silme)? (2) hangi **alanlar** kapalı — dışarıda kalan bir
alan sonucu değiştirebiliyor mu? (3) test her fiil/alan için **ayrı ayrı** mı
koşuyor? Korunan alan listesi testte de veri olarak dursun; tek örnek üzerinden
yazılmış test, listeye eklenmemiş alanı görmez.

---

## L-013 — Girdisini baştan okuyan iş, kısıtsız tabloda SAYAÇ üretir

**Olay:** Günlük bir iş, girdi dosyalarının TAMAMINI her koşumda yeniden
okuyordu (dosya bazlı artımlılık yoktu) ve yazma fonksiyonu düz `INSERT` idi.
Hedef tabloda benzersiz kısıt olmadığı için aynı gözlem her gün yeniden
yazıldı. Ölçüldüğünde: satırların yalnız ~%10'u tekildi, en eski kayıt 23
kopyaya ulaşmıştı. İki zarar birden — depo/dump her gün şişiyordu ve "kayıt
sayısı" metriği veri hacmini değil **koşum sayısını** ölçüyordu. Doğal anahtarı
PRIMARY KEY olan kardeş tablolar etkilenmemişti: kusur iş akışında değil,
tablonun tasarımındaydı.

**Ders:** "Her koşumda baştan oku" basit ve dayanıklı bir tasarımdır **ama**
yazdığı her tabloda idempotentlik şart koşar. Kısıtsız bir tabloda bu desen,
ölçüm kılığında bir koşum sayacı üretir (L-010'un veri katmanındaki hâli).

**Kural:** Bir iş girdisinin tamamını yeniden okuyorsa her hedef tablo için sor:
**"Aynı gözlem ikinci kez yazılırsa ne olur?"** Cevap "satır artar" ise ya doğal
anahtara `UNIQUE` + "varsa yoksay" koy, ya da artımlılığı kanıtla. Denetim tek
sorgu: `COUNT(*) == COUNT(DISTINCT <doğal anahtar>)`. Kısıtı sonradan eklerken
mevcut kopyaları **önce temizle** ve eski yedeklerin hâlâ yüklenebildiğini
doğrula.

---

## L-012 — Fixture üreticiden türemiyorsa test, mock'u doğrular

**Olay:** Bir test yıllardır yeşil geçiyor ve "şu dal çalışıyor" izlenimi
veriyordu. Testin elle kurduğu fixture bir alanı içeriyordu; oysa o alanı
üreten **tek** fonksiyon onu hiç üretmiyordu. Yani üretimde o dal ERİŞİLEMEZDİ
ve test bunu maskeliyordu.

**Ders:** Elle yazılmış fixture, üreticinin sözleşmesinden sapabilir; saptığı an
ona dayanan bütün testler gerçekliğini kaybeder — üstelik yeşil kalarak, yani
yanlış güven vererek.

**Kural:** Fixture'ı mümkünse **gerçek üreticinin çıktısından türet.** Mümkün
değilse bir **sözleşme testi** yaz: "üreticinin ürettiği anahtar kümesi,
tüketicinin okuduğunu kapsıyor mu?" Bir alanın üretilmemesi kasıtlıysa bunu
**kilitleyen** bir test yaz ki üretici bağlandığı gün test düşsün ve ölü dalın
kaldırılması hatırlansın.

---

## L-011 — Yazılmış ama BAĞLANMAMIŞ koruma, olmayan korumadır

**Olay:** Bir güvenlik/doğruluk garantisi hem karar kaydında hem docstring'de
"yapısal garanti" diye anlatılıyordu. Koruma kodda gerçekten yazılmıştı — ama
**parametre opsiyoneldi ve hiçbir çağıran onu geçmiyordu.** Üstelik korumasız
ikinci bir kopya vardı.

**Ders:** Opsiyonel koruma = kapalı koruma. Docstring'in "garanti" demesi
garanti etmez; garantiyi **çağrı yolu** verir. İkinci bir kopya varsa garanti
zaten yoktur.

**Kural:** Koruma yazdığında **varsayılanı güvenli yap** ve güvensiz yolu
tamamen kaldır (opsiyon bırakma). Sonra "bu korumayı atlayan bir yol var mı?"
diye `grep` at. Aynı veriyi okuyan çok sayıda tüketici varsa korumayı
tüketicilere değil **KAYNAĞA** koy — bir yazma noktasını düzeltmek, on okuma
noktasını yamamaktan hem kısa hem kalıcıdır (bkz. L-008).

---

## L-010 — Tek bir değerden başkasını üretemeyen "ölçüm" ölçüm değil, KİMLİKTİR

**Olay:** Bir sistemin dürüstlük iddiasının tamamının dayandığı karne metriği
"+0.0 puan / +0.00%" yazıyor ve gerçek bir ölçüm gibi okunuyordu. Ölçünce
görüldü ki formül, sistemin üretebildiği hüküm kümesinde **matematiksel olarak**
sabit çıkıyordu — girdi ne olursa olsun. Dahası bir kapı, açılma şartı olarak
tam bu sabit sayıyı okuyordu: kapalı kapı → tek tip hüküm → sıfır skor → kapalı
kapı. Aylar sonra bu tablodan "ölçtük, olmadı" sonucu çıkarılacaktı.

**Ders:** Bir metriğin sayı üretmesi, bilgi taşıdığı anlamına gelmez. Girdiden
bağımsız sabit çıkan bir alan **ölçüm kılığında bir kimliktir** — ve en tehlikeli
hâli budur, çünkü tabloda gerçek ölçümden ayırt edilemez.

**Kural:** Karar metriği yazarken sor: **"Bu sayının farklı çıkabilmesi için ne
olması gerekir?"** Cevabı üretemiyorsan metrik değil kimlik yazmışsındır. Somut
test: metriği uç senaryolarla besle; hepsinde aynı çıkıyorsa formül dejenere ya
da girdi kümesi eksiktir. Ölçülemez durumu **rakamla değil SEBEPLE** raporla —
"0.00" yazmak "ölçtük ve kötü çıktı" diye okunur. Ve bir kapının şartı, kapı
kapalıyken üretilemeyen bir sayıya bağlanamaz; o kapı asla açılmaz.

---

## L-009 — Türetilmiş dosya izleniyor ama kaynağı izlenmiyorsa, senkron SENİN sorumluluğun

**Olay:** Bir veritabanının metin dump'ı git'te izleniyor, binary hâli
gitignore'daydı. `git pull` dump'ı tazeledi ama binary'yi tazelemedi; sonra
dump **bayat binary'den** yeniden üretilip commit'lendi → ~1.5 günlük üretim
verisi sessizce silindi (satır sayıları geriye gitti).

**Ders:** `git status` temiz görünür, `git pull` başarılı olur, ama izlenen
türev ile izlenmeyen kaynak birbirinden ayrışmıştır. Ayrışma ancak türev
yeniden üretildiğinde ve iş işten geçtikten sonra fark edilir.

**Kural:** (1) Türevi yerelde **üretme** — üretimi otomasyona bırak. (2) Zorunluysa
önce kaynağı türevden **geri yükle**, sonra üret. (3) Türev bir commit'te
değişiyorsa **satır/kayıt sayıları azalmamalı**; azalıyorsa dur ve bak.
Kasıtlı bir küçülme varsa commit mesajında gerekçesini yaz ki denetim onu
kazadan ayırabilsin.

---

## L-008 — Yeni bir sinyal/kural bağlarken TÜM tüketicilerini bağla

**Olay:** Ölü bir alarm kuralı canlandırıldı ve bağlamı hesaplayan yere doğru
şekilde eklendi. Ama aynı değeri gösteren diğer tüketiciler (rapor, CLI, kalibrasyon
provası) güncellenmedi. Sonuç: kural tetiklendiğinde kullanıcı "eşik aşıldı"
uyarısı alacak ama **tetikleyen sayıyı hiçbir yerde göremeyecekti.**

**Ders:** Bir değer üretmek onu "bağlamak" değildir. Aynı veriyi tüketen her yol
(alarm / rapor / CLI / dışa aktarım / kalibrasyon) ayrı bir uçtur; biri unutulursa
tutarsızlık kullanıcıya ulaşır.

**Kural:** Yeni bir sinyal/metrik eklerken önce **tüketici listesini çıkar**
(`grep` ile aynı alanı kullanan tüm dosyalar), sonra hepsini bağla ya da bağlamadığını
gerekçesiyle yaz. "Kardeş" bir alan varsa (ör. aynı kapıya tabi ikinci bir z-skor)
ona da aynı muameleyi yap.

---

## L-007 — Repodaki script'lerin sessiz yan etkilerini denetle

**Olay:** Repoda duran bir yedekleme script'i sonunda `git commit && git push`
yapıyordu — kimseye sormadan. Ayrıca ürettiği 2.9 MB'lık binary dosyalar
gitignore'da olmadığı için repoya girecekti. Script hiç çalıştırılmamıştı;
"dolu silah" gibi duruyordu.

**Ders:** Bir script'in adı ne yaptığını söylemez. `backup.sh` sadece yedek
almaz — push da eder. Çalıştırılmamış olması zararsız olduğu anlamına gelmez.

**Kural:** Repoda duran her script'i **sonuna kadar oku** ve şunu sor: dışa
dönük bir şey yapıyor mu (push, deploy, mail, ödeme, silme)? Ürettiği dosyalar
gitignore'lu mu? Değilse ya kuralı ekle ya script'i temizle.

---

## L-006 — "Kullanılmıyor" ile "silinebilir" aynı şey değil

**Olay:** Üretim yolunda çağrılmayan bir modül kümesi (7/24 toplayıcı modu +
systemd birimleri) "ölü kod" gibi görünüyordu. İncelenince bunların
**ertelenmiş bir kararın** (ayrı sunucuya taşınma) hazır altyapısı olduğu ve
birbirine bağlı tek bir paket oluşturduğu görüldü — biri silinse diğerleri
anlamsız kalırdı.

**Ders:** Kullanılmayan kod üç sebepten olabilir: (a) gerçekten ölü,
(b) ertelenmiş bir kararın altyapısı, (c) elle çalıştırılan araç. Yalnız (a)
silinir. "İptal edildi" ile "ertelendi" arasındaki fark burada belirleyicidir.

**Kural:** Silmeden önce sor: "Bu neyin parçası ve hangi karar bunu doğurdu?"
Cevap bir ertelenmiş senaryoysa DOKUNMA, gerekçesini `ai/PROJECT.md` veya
`ai/DECISIONS.md`'ye yaz ki bir dahakine tekrar tartışılmasın.

---

## L-005 — `.gitignore` satır-sonu yorumu KURALI BOZAR

**Olay:** `.gitignore` düzenlenirken pattern'lerin yanına açıklama yazıldı
(`data/altin.sqlite   # binary izlenmez`). Git satır-sonu yorumu desteklemez;
yorum metni pattern'in parçası sayıldı ve **üç gizlilik kuralı sessizce
devre dışı kaldı** (kişisel profil, kişisel export, binary DB). Hata mesajı yok.

**Ders:** Sessizce bozulan koruma, hiç olmayan korumadan tehlikelidir — var
sanırsın.

**Kural:** `.gitignore`'da yorumlar **kendi satırında** olur. Düzenledikten
sonra kuralları tek tek doğrula:
`git check-ignore -q <yol> && echo korunuyor || echo AÇIK`
Aynı disiplin her "sessiz başarısız olan" config için geçerlidir.

---

## L-004 — Kural dosyaları alt klasörde çalışmaz

**Olay:** Usta sistemi bir projede alt klasöre kopyalandı. Hiçbir IDE alt
klasördeki AGENTS.md/CLAUDE.md'yi otomatik okumadığı için sistem atıl kaldı —
kimse fark etmedi, çünkü hata vermiyor, sadece sessizce devreye girmiyor.

**Ders:** Araç konvansiyonuna bağlı dosyaların (kural, config, manifest) YERİ
işlevin parçasıdır. Yanlış yerdeki doğru dosya = yok hükmünde.

**Kural:** Kural/köprü dosyalarını daima proje köküne koy. Kurduktan sonra
"gerçekten yükleniyor mu?" diye test et (ör. `/durum` yazıp STATE.md'yi okuyup
okumadığına bak) — dosyanın varlığını görmek yeterli değil.

---

## L-003 — Metrik değişince "sistem bozuldu" sanılır; taban çizgisini ölç

**Olay:** Bir sağlık metriği %16'dan %62'ye sıçradı ve "sistem düzensiz
çalışıyor" teşhisi kondu. Ölçünce ham üretim hızının hiç değişmediği, yalnızca
metriğin PAYDASININ (kalibrasyon commit'i) değiştiği görüldü.

**Ders:** Bir metrikteki sıçrama çoğu zaman sistemin değil ÖLÇÜMÜN değiştiğini
gösterir.

**Kural:** "X bozuldu" iddiasında önce ham taban çizgisini zaman serisi olarak
çıkar, sonra metrik tanımının değiştiği commit'i ara. İkisi de temizse iddia
düşer. Ayrıca iki farklı olguyu benzer kelimelerle raporlama ("kesinti" vs
"boşluk") — okuyanı yanıltır, yanlış alarm üretir.

---

## L-002 — "Elle bir kere çalıştırılan" script'ler sessizce donar

**Olay:** Bir veri tablosu yalnızca elle çalıştırılan bir backfill script'i
tarafından besleniyordu, otomatik pipeline'a bağlı değildi. 17 gün donuk kaldı;
o veriden beslenen alarmlar yanlış eşikle çalıştı ve hiçbir hata fırlamadı.

**Ders:** "Bir kere elle çalıştırdım, gerisi otomatik" varsayımı yanlıştır.
Otomatiğe bağlı olmayan üretici günün birinde sessizce durur (sessiz bozulma).

**Kural:** Yeni bir veri kaynağı/tablo eklenince sor: "Bunu kim, ne sıklıkla
güncelliyor?" Cevap "kimse / elle" ise ya otomatiğe bağla ya da STATE.md'ye
"manuel bakım gerekir" diye açıkça yaz.

---

## L-001 — Otomasyon commit atıyorsa yerel kopya eskir

**Olay:** CI (GitHub Actions) düzenli commit atan bir projede yerel checkout'a
bakılıp "sistem 3 gündür durmuş" sonucuna varıldı. Oysa uzak repo gayet güncel
işliyordu; yerel kopya 40 commit gerideydi.

**Ders:** Otomasyonun yazdığı repolarda yerel durum, üretim durumu DEĞİLDİR.

**Kural:** Sağlık denetimine daima `git fetch` + yerel/uzak fark kontrolüyle
başla (`git rev-list --count HEAD..origin/main`). Yerel veri eskiyse "sistem
durdu" deme; önce uzağa bak.

<!-- Yeni ders şablonu:

## L-NNN — Kısa başlık

**Olay:** Ne oldu?

**Ders:** Genelleştirilmiş çıkarım.

**Kural:** Usta bundan sonra somut olarak ne yapacak/soracak?
-->
