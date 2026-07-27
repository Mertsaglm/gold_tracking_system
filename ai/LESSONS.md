# LESSONS.md — Dersler ve Anti-Pattern'ler

> Geçmiş hatalardan çıkan dersler. Usta bunları bilir ve aynı çukura ikinci
> kez düşülmesine izin vermez. `/ders <olay>` komutuyla yeni ders eklenir.
> Bu dosya projeler arası taşınır — dersler birikir.
>
> ⚠️ **NUMARA UZAYI ORTAKTIR.** Bu dosya ile devir paketindeki
> `Proje Yardımcısı - .../ai/LESSONS.md` **aynı L-NNN numaralarını paylaşır**;
> buradaki sürüm proje ayrıntılı, oradaki genelleştirilmiştir. Yeni ders
> eklerken **iki dosyadaki en büyük numaraya** bak ve bir sonrakini al —
> yalnız buraya bakıp numara vermek çakışma üretir (2026-07-27'de tam bu oldu:
> yeni ders L-005 sanıldı, oysa pakette L-005 `.gitignore` dersiydi → L-009'a
> taşındı). Kontrol: `grep -h '^## L-' ai/LESSONS.md 'Proje Yardımcısı'*/ai/LESSONS.md | sort -u`

---

## L-012 — 2026-07-27 — Fixture üreticiden türemiyorsa test, mock'u doğrular

**Olay:** `test_kapi_acik_ve_maliyeti_asarsa_sat` yıllardır yeşil geçiyor ve
"SAT dalı çalışıyor" izlenimi veriyordu. Testin elle kurduğu fixture
`beklenen_gram_kazanc_pct` alanını içeriyordu; oysa o alanı üreten **tek**
fonksiyon (`gram.engel_ozet`) onu hiç üretmiyordu. Yani üretimde SAT dalı
ERİŞİLEMEZDİ ve test bunu maskeliyordu.

**Ders:** Elle yazılmış fixture, üreticinin sözleşmesinden sapabilir ve saptığı
an ona dayanan bütün testler gerçekliğini kaybeder — üstelik yeşil kalarak,
yani yanlış güven vererek.

**Kural:** Fixture'ı mümkünse **gerçek üreticinin çıktısından türet**. Mümkün
değilse en azından bir **sözleşme testi** yaz: "üreticinin ürettiği anahtar
kümesi, tüketicinin okuduğunu kapsıyor mu?" Bu tek test, sınıfın tekrarını
kalıcı engeller. Ek olarak: bir alanın üretilmemesi kasıtlıysa (burada ADR
#007-H'nin ölçüm sonucuydu) bunu **kilitleyen** bir test yaz ki üretici
bağlandığı gün test düşsün ve ölü dalın kaldırılması hatırlansın.

---

## L-011 — 2026-07-27 — Yazılmış ama BAĞLANMAMIŞ koruma, olmayan korumadır

**Olay:** `asof = T−1` (son tam kapanmış gün) garantisi hem ADR'de hem modül
docstring'inde "yapısal garanti" diye anlatılıyordu. Kodda koruma gerçekten
yazılmıştı — `son_kapali_gun(con, bugun=...)` bugünü dışlayan filtreyi
destekliyordu — ama **parametre opsiyoneldi ve iki çağıranın hiçbiri onu
geçmiyordu.** Üstelik ikinci, korumasız bir kopya (`tahmin._son_kapali_gun`)
vardı. Ölçüldü: kesişimin her iki bacağı da hafta içi aynı-gün satırını
içeriyordu, yani ilk hafta içi koşumda bugünün YARIM barı `asof` olacaktı ve
`predictions`'a DEĞİŞTİRİLEMEZ yazılacaktı.

**Ders:** Opsiyonel koruma = kapalı koruma. Docstring'in "garanti" demesi
garanti etmez; garantiyi **çağrı yolu** verir. İkinci bir kopya varsa garanti
zaten yoktur.

**Kural:** Bir koruma yazdığında **varsayılanı güvenli yap** ve güvensiz yolu
tamamen kaldır (opsiyon bırakma). Sonra "bu korumayı atlayan bir yol var mı?"
diye `grep` at. Aynı veriyi okuyan çok sayıda tüketici varsa korumayı
tüketicilere değil **KAYNAĞA** koy: bu projede `history_daily`/`ohlc_daily`'ye
bugünün yarım barının hiç yazılmaması, 16 okuma yolunu tek hamlede doğru kıldı.

---

## L-010 — 2026-07-27 — Tek bir değerden başkasını üretemeyen "ölçüm" ölçüm değil, KİMLİKTİR

**Olay:** Karar motorunun karnesi — projenin dürüstlük iddiasının tamamının
dayandığı mekanizma — "tabana fark +0.0p · gram etkisi +0.00%" yazıyordu ve bu
gerçek bir ölçüm gibi okunuyordu. Ölçünce sebebi görüldü: `hukum_dogru_mu`
`SAT*` olmayan her hükme tabanla aynı cevabı veriyor, sistem ise yalnız
`AL_*`/`TUT` üretebiliyordu. Yani o iki sayı **piyasa ne yaparsa yapsın** 0.00
çıkıyordu (11 farklı senaryoda doğrulandı). Dahası kapı, açılma şartı olarak
tam bu iki sayıyı okuyordu → kapalı kapı → TUT → sıfır skor → kapalı kapı.
Ekim'de yazılması planlanan "trade kolu kalıcı kapalı" ADR'si bir ölçüme değil,
bir totolojiye dayanacaktı.

**Ders:** Bir metriğin sayı üretmesi, onun bilgi taşıdığı anlamına gelmez.
Girdiden bağımsız olarak sabit çıkan bir alan **ölçüm kılığında bir kimliktir**
ve en tehlikeli hâli budur: tabloda gerçek bir ölçümden ayırt edilemez.

**Kural:** Bir karar metriği yazarken sor: **"Bu sayının farklı çıkabilmesi için
ne olması gerekir?"** Cevabı üretemiyorsan metrik değil kimlik yazmışsındır.
Somut test: metriği uç senaryolarla (en iyi/en kötü piyasa) besle; hepsinde aynı
çıkıyorsa ya girdi kümesi eksiktir ya formül dejenere. Ölçülemez durumu
**rakamla değil sebeple** raporla ("ÖLÇÜM İÇERMİYOR"), yoksa 0.00 "ölçtük ve
kötü çıktı" diye okunur. Bir kapının açılma şartı, kapı kapalıyken üretilemeyen
bir sayıya bağlanamaz — o kapı asla açılmaz.

---

## L-009 — 2026-07-26 — `git pull` dump'ı tazeler, SQLite'ı tazelemez

**Olay:** Oturum başında kural gereği `git pull` yapıldı (13 commit geride) ve
`data/altin.sql` uzak sürüme güncellendi. Ama `data/altin.sqlite` **gitignore'da**
olduğu için pull'dan etkilenmedi — 25 Tem 00:26'da kalmıştı. Sonra bir DoD
kontrolü için `python -m src.dbdump` çalıştırıldı; dump **yerel sqlite'tan**
üretildiği için taze dump geriye sarıldı ve commit'lendi:
`prim_history` 251 → **238**, `ticks` 14 511 → **13 109**. Yani ~1.5 günlük
üretim verisi sessizce silindi.

**Ders:** L-001'in daha sinsi hali. Orada yerel *repo* eskiyordu ve fark
görülebiliyordu; burada eskiyen şey **git'in izlemediği türetilmiş dosya**.
`git status` temiz görünür, `git pull` başarılı olur, ama sqlite ile dump
birbirinden ayrışmıştır. Bu ayrışma ancak dump alındığında ve iş işten geçtikten
sonra fark edilir.

**Kural:**
1. Yerelde **`python -m src.dbdump` çalıştırma.** Dump üretimi Actions'ın işi
   (`daily.yml` adımı). Yerelde gerekiyorsa **önce `python -m src.restore_db`**
   ile sqlite'ı dump'tan tazele, sonra dump al.
2. `git pull` sonrası DB'ye dokunacaksan refleks: `restore_db`.
3. `data/altin.sql` bir commit'te değişiyorsa **satır sayıları azalmamalı.**
   Azalıyorsa dur ve bak: `grep -c "INSERT INTO <tablo>" data/altin.sql`
   commit öncesi/sonrası karşılaştır.

**Genel ilke:** Türetilmiş bir dosya git'te izleniyor ama kaynağı izlenmiyorsa,
o ikilinin senkronu **git'in değil senin sorumluluğun**dur.

---

---

## L-008 — 2026-07-25 — Yeni bir sinyal/kural bağlarken TÜM tüketicilerini bağla

**Olay:** Ölü bir alarm kuralı (`quarter_z`) canlandırıldı ve bağlamı hesaplayan
yere doğru şekilde eklendi. Ama aynı değeri gösteren diğer tüketiciler (rapor,
CLI, kuru prova) güncellenmedi. Kapı açıldığında kullanıcı "çeyrek |z| > 2"
uyarısı alacak ama **tetikleyen sayıyı hiçbir yerde göremeyecekti.**

**Ders:** Bir değer üretmek onu "bağlamak" değildir. Aynı veriyi tüketen her yol
(alarm / rapor / CLI / dışa aktarım / kalibrasyon) ayrı bir uçtur; biri
unutulursa tutarsızlık kullanıcıya ulaşır.

**Kural:** Yeni bir sinyal/metrik eklerken önce **tüketici listesini çıkar**
(`grep -rn "<alan>" src/`), sonra hepsini bağla ya da bağlamadığını gerekçesiyle
yaz. Tüketici sayısı fazlaysa (bu projede `history_daily`'yi 16 yer okuyor)
tek tek yamamak yerine **kaynağı düzelt** — bkz. L-011.

---

## L-007 — 2026-07-24 — Repodaki script'lerin sessiz yan etkilerini denetle

**Olay:** Repoda duran bir yedekleme script'i sonunda `git commit && git push`
yapıyordu — kimseye sormadan. Ayrıca ürettiği ~2.9 MB'lık binary dosyalar
gitignore'da olmadığı için repoya girecekti. Script hiç çalıştırılmamıştı;
"dolu silah" gibi duruyordu.

**Ders:** Bir script'in adı ne yaptığını söylemez. `backup.sh` sadece yedek
almaz — push da eder. Çalıştırılmamış olması zararsız olduğu anlamına gelmez.

**Kural:** Repoda duran her script'i **sonuna kadar oku** ve sor: dışa dönük
bir şey yapıyor mu (push, deploy, mail, ödeme, silme)? Ürettiği dosyalar
gitignore'lu mu? Değilse ya kuralı ekle ya script'i temizle.

---

## L-006 — 2026-07-24 — "Kullanılmıyor" ile "silinebilir" aynı şey değil

**Olay:** Üretim yolunda hiç çağrılmayan bir modül kümesi (`collector.py`,
`supervisor.py`, `deploy/*.service|timer`) "ölü kod" gibi görünüyordu.
İncelenince bunların **ertelenmiş bir kararın** (Oracle Cloud'a taşınma)
hazır altyapısı olduğu ve birbirine bağlı tek bir paket oluşturduğu görüldü —
biri silinse diğerleri anlamsız kalırdı (`ai/PROJECT.md` "Kapsam Dışı").

**Ders:** Kullanılmayan kod üç sebepten olabilir: (a) gerçekten ölü,
(b) ertelenmiş bir kararın altyapısı, (c) elle çalıştırılan araç. Yalnız (a)
silinir. **"İptal edildi" ile "ertelendi" arasındaki fark belirleyicidir.**

**Kural:** Silmeden önce sor: "Bu neyin parçası ve hangi karar bunu doğurdu?"
Cevap ertelenmiş bir senaryoysa DOKUNMA; gerekçesini `ai/PROJECT.md` veya
`ai/DECISIONS.md`'ye yaz ki bir dahakine tekrar tartışılmasın.

---

## L-005 — 2026-07-24 — `.gitignore` satır-sonu yorumu KURALI BOZAR

**Olay:** `.gitignore` düzenlenirken pattern'lerin yanına açıklama yazıldı
(`data/altin.sqlite   # binary izlenmez`). Git satır-sonu yorumu desteklemez;
yorum metni pattern'in parçası sayıldı ve **üç gizlilik kuralı sessizce devre
dışı kaldı** (kişisel profil, kişisel Telegram export'u, binary DB). Hata yok.

**Ders:** Sessizce bozulan koruma, hiç olmayan korumadan tehlikelidir — var
sanırsın ve ona güvenerek davranırsın.

**Kural:** `.gitignore`'da yorumlar **kendi satırında** olur. Düzenledikten
sonra kuralları tek tek doğrula:
`git check-ignore -q <yol> && echo korunuyor || echo AÇIK`
Aynı disiplin her "sessiz başarısız olan" config için geçerlidir.

---

## L-004 — 2026-07-24 — Kural dosyaları alt klasörde çalışmaz

**Olay:** Usta sistemi `Proje Yardımcısı/` alt klasörüne kopyalanmıştı. Hiçbir
IDE alt klasördeki AGENTS.md/CLAUDE.md'yi otomatik okumadığı için sistem atıl
kaldı — hata vermiyor, sadece sessizce devreye girmiyordu.

**Ders:** Araç konvansiyonuna bağlı dosyaların (kural, config, manifest) YERİ
işlevin parçasıdır. Yanlış yerdeki doğru dosya = yok hükmünde.

**Kural:** Kural/köprü dosyalarını daima proje köküne koy; kurduktan sonra
"gerçekten yükleniyor mu?" diye test et (`/durum` yazıp STATE.md'yi okuyor mu),
dosyanın varlığını görmek yeterli değil.

---

---

## L-003 — 2026-07-24 — Metrik değişince "sistem bozuldu" sanılır; taban çizgisini ölç

**Olay:** "Kapsama %16'dan %62'ye çıktı, arşiv düzensiz çalışıyor, kesinti
545 dk" diye bir arıza iddiası geldi. Ölçünce ham toplama hızının 07-08'den
beri sabit olduğu (medyan 13 kayıt/gün) görüldü — değişen tek şey metriğin
PAYDASI'ydı (07-21 kalibrasyon commit'i). Ayrıca "545 dk kesinti" altyapı
arızası değil, kaynağın boş dönmesiydi.

**Ders:** Bir sağlık metriğindeki sıçrama, çoğu zaman sistemin değil ÖLÇÜMÜN
değiştiğini gösterir. Rapor çıktısındaki yüzdelere bakıp arıza teşhisi koyma;
altındaki HAM sayıya (kaç kayıt/gün) ve metrik formülünün ne zaman
değiştiğine (git log) bak.

**Kural:** "X bozuldu" iddiasında önce ham taban çizgisini zaman serisi olarak
çıkar; sonra metrik tanımının değiştiği commit'i ara. İkisi de temizse iddia
düşer. Ayrıca: iki farklı olguyu benzer kelimelerle raporlama ("kesinti" vs
"boşluk") — okuyanı yanıltır, yanlış alarm üretir.

---

---

## L-002 — 2026-07-24 — "Elle bir kere çalıştırılan" script'ler sessizce donar

**Olay:** `history_daily` tablosu yalnızca elle çalıştırılan bir backfill
script'i (`src/history.py`) tarafından yazılıyordu, otomatik günlük pipeline'a
hiç bağlı değildi. 17 gün boyunca donuk kaldı ve bunu fark eden hiçbir alarm
yoktu — botun kendi mesajları (ATR(75) tekrarı) tek işaretti, onu da elle
export inceleyince gördük.

**Ders:** "Bir kere elle çalıştırdım, gerisi otomatik" varsayımı yanlıştır —
o script otomatik pipeline'a bağlı DEĞİLSE, üretilen veri günün birinde donar
ve hiçbir hata fırlatmaz (sessiz bozulma). Bir tabloyu/dosyayı besleyen HER
script'in ya otomatik pipeline'a bağlı olduğunu ya da neden bağlı olmadığını
(gerçekten tek seferlik mi?) doğrula.

**Kural:** Yeni bir veri kaynağı/tablo eklenince sor: "Bunu kim, ne sıklıkla
güncelliyor?" Cevap "kimse / elle" ise ya otomatiğe bağla ya da STATE.md'ye
"manuel bakım gerekir" diye açıkça yaz.

---

---

## L-001 — 2026-07-24 — Yerel repo üretimin gerisinde kalır

**Olay:** Denetimde yerel checkout'a bakıldı; veri 21 Tem'de "durmuş" göründü.
Aslında GitHub Actions kesintisiz commit'liyordu (40 commit ileride); yerel
kopya pull edilmemişti.

**Ders:** Actions'ın otomatik commit attığı projelerde yerel kopya sürekli
geride kalır; yerel duruma bakıp "sistem durdu" sonucu yanlış olur.

**Kural:** Proje sağlığını denetlemeden önce daima `git fetch` + yerel/uzak fark
kontrolü (`git rev-list --count HEAD..origin/main`) yap. Yerel eskiyse önce
`origin/main`'e bak, sonra konuş.

<!-- Yeni ders şablonu:

## L-NNN — Kısa başlık

**Olay:** Ne oldu?

**Ders:** Genelleştirilmiş çıkarım.

**Kural:** Usta bundan sonra somut olarak ne yapacak/soracak?
-->
