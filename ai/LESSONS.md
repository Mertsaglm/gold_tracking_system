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

## L-020 — 2026-08-28 — Bir arızayı düzeltirken ölçümün VAR OLMA ŞARTINI yok etme

**Olay:** ADR #013, prim'i bozan gerçek bir arızayı (vadeli kontrat roll'ü)
doğru teşhis etti ve "ons ile gram AYNI kaynaktan, AYNI zaman damgasıyla
gelsin" diyerek düzeltti. Düzeltme çalıştı: prim −1.75%'ten −0.49%'a döndü,
yanlış alarmlar durdu, sd çöktü. **Herkes bunu başarı sandı** — STATE.md dâhil.

Oysa prim **tanım gereği iki BAĞIMSIZ fiyatın farkıdır**. İki bacağı aynı
satıcıya taşımak, ölçülen şeyi ortadan kaldırdı: `gram_has ≡ ons × kur × 0.995`
olduğu için ons formülde sadeleşti ve geriye satıcının kendi saflık çarpanı
kaldı. 8 gün boyunca prim **her gün tam −0.5000%** çıktı; bir gün gün-içi
varyans **tam sıfırdı**.

**Anti-pattern:** *"Sayı düzeldi → düzeltme çalıştı."* Varyansın çökmesi iki
şeyin işareti olabilir: gürültü gitti **ya da** ölçüm gitti. Bu ikisini ayırt
eden soru "sayı makul mü?" değil, **"bu sayının farklı çıkabilmesi için ne
olması gerekir?"**dir (L-010'un aynı sorusu, farklı metrik).

**Doğru refleks:** Bir veri kaynağını değiştirirken şunu sor:
> **"Bu metriğin var olabilmesi için hangi iki şeyin bağımsız olması
> gerekiyor? Değişiklikten sonra hâlâ bağımsızlar mı?"**

**Kalıcı koruma:** Bağımsızlık **üretim verisi üzerinde** her gün ölçülür
(`calc.turetilmis_mi` + `import_actions.turetilmis_gunler`), kimliğe düşen
günler kapı sayacının dışına alınır ve rapor en üstte kırmızı satır basar.

**İkinci ders — sentetik test bu sınıfı YAKALAYAMAZ.** 855 test yeşildi ve
adı tam bu iş için konmuş `test_dejenere_metrik.py` bile sessizdi. Sebep:
fixture `gram_has_sell = teorik × 1.0045` üretiyordu — **sabit çarpan, yani
kimliğin ta kendisi**; ama testler onu hiç sorgulamıyordu. Sentetik veride iki
seri bağımsız kurulursa kimlik hiç oluşmaz ve koruma testi *vacuous* geçer
(AGENTS.md §5). Bu turda fixture rejimli hâle getirildi ve nöbetçi ayrıca
**üretim arşivine karşı iki yönlü** test edildi: 08-17 sonrası ateşlemeli,
07-07…07-28 arası ateşlememeli.

**Üçüncü ders — iki denetçi aynı olguyu zıt okuyabilir.** GPT raporu prim'in
−0.49% olmasını "düzeltme çalıştı, korunmalı" diye yazdı ve o seriyi z-skor
kalibrasyonuna taban önerdi. Konsensüs aramak yanlış cevabı verirdi; ayıran şey
**ikisinin öngörüsünü ayırt eden bir ölçüm koşmak** oldu (ons'un sadeleşip
sadeleşmediği). Rapor ne derse desin ölçüt kendi ölçümündür.

---

## L-019 — 2026-08-16 — Döngüsel test, kaynağın enstrüman değiştirmesini göremez

**Olay:** 2026-07-29'da `yfinance GC=F` canlı kotasyonu, Ağustos kontratı vadesini
doldurunca **Aralık kontratına** atladı. Contango farkı (+%1.39) `theoretical`'e
girdi; prim 17 gün boyunca 1.25 puan sahte iskonto gösterdi. `|prim|>%1.5` alarmı
4 gün üst üste yanlış ateşleyip Telegram'a gitti. Kod değişmedi, kaynak değişti.

**Neden 851 test yakalamadı — hepsi DÖNGÜSELDİ:**

```python
beklenen = calc.theoretical_gram(r["ons_usd"], r["usdtry"], troy)
assert r["gram_teorik"] == pytest.approx(beklenen)
```

Bu, çarpmanın doğru yapıldığını doğrular; **`ons`'un doğru enstrüman olduğunu
değil.** Girdi yanlış kontrattan gelse test yine yeşildir. Aynı şey
`prim == piyasa/teorik − 1` testi için de geçerli: kendi içinde tutarlı, dışarıya
karşı kör.

**Bağımsız tanık zaten elimizdeydi:** Truncgil hem `gram-has-altin` hem de `ons`
veriyor. Dahası `test_truncgil_prim_ornek_yanitta_makul` o `ons` alanını
**biliyordu** — `$` işaretini elle temizleyip kullanıyordu bile. Düzeltme bir satır
uzaktaydı; kimse iki ucu birbirine bağlamadı.

**Ders:** Türetilmiş bir büyüklüğü kendi girdileriyle doğrulayan test, ölçüm değil
**totolojidir.** Dış dünyadan gelen her seri için sorulacak soru şudur:

> *"Bu sayının doğru olduğunu, onu üreten kaynaktan BAĞIMSIZ neyle sınıyorum?"*

Cevap yoksa o seri denetimsizdir. Fiyat serilerinde ikinci soru: **"bu sembol
sabit bir enstrüman mı, yoksa altındaki şey değişebilir mi?"** Vadeli kontratlar,
endeksler ve "sürekli" seriler zamanla farklı şeyleri gösterir; ticker aynı kalır.

**Anti-pattern:** tek kaynaktan gelen bir seriyi yalnız kendi içindeki aritmetikle
test etmek — özellikle o seri sistemin çekirdek metriğini besliyorsa.

**Nasıl kapatıldı (ADR #013):** ons Truncgil spot'a taşındı (gram ile aynı kaynak,
aynı zaman damgası); yfinance'e sessiz yedek YASAKLANDI; `fetch_row`'un ons'u
nereden aldığını kilitleyen 2 test yazıldı ve **mutasyonla düştüğü kanıtlandı**.

---

## L-018 — 2026-08-11 — Teslim yolu test edilmiyorsa sistem 13 gün konuşmadan "çalışır"

**Olay:** 2026-07-29 → 08-10 arası HİÇBİR anomali bildirimi Telegram'a gitmedi.
125 Actions koşusu bu hatayı verdi ve **hepsi yeşil göründü**. Kesinti tam
altının %+9.55 koştuğu döneme denk geldi; 08-05'te gram +232₺ (2×ATR eşiği 133₺)
ve 08-07'de +153₺ hareket etti, ikisinde de uyarı çıkmadı.

**Kök sebep — dört katman üst üste bindi:**
1. `prim_sapma`'nın geçersizlik metni `(|%|<1.5)` içeriyordu; `parse_mode="HTML"`
   ile giden metinde kaçırılmamış `<` var. Telegram'ın kendi cevabı:
   `Bad Request: can't parse entities: Unsupported start tag "1.5)"`.
2. `send_message` istisnayı `for al in to_send:` döngüsünden dışarı attı →
   sıradaki `makas` ve `gunluk_hareket` **hiç denenmedi** (`prim_sapma` birinciydi).
3. İstisna `_save_state()`'e ulaşmadı → arıza ne diske ne repoya yazıldı; üstelik
   damga da ilerlemediği için durum her koşumda aynen tekrarlandı.
4. `archive.yml`'daki `continue-on-error: true` adımı yeşil bıraktı.

**Neden 815 test yakalamadı:** `test_notify.py`'daki 12 testin hepsi
`evaluate_thresholds` ve `apply_cooldown` **saf fonksiyonlarına** bakıyordu.
`_format_alert`'ün ÜRETTİĞİ metni hiçbir test görmüyordu. Karar mantığı
kilitliydi, **teslim biçimi denetimsizdi**.

**Ders:** Bir sistemin dış dünyaya çıkan yolu (serialize → protokol → API) en az
karar mantığı kadar test edilmelidir. "Doğru kararı üretmek" ile "kararı teslim
etmek" iki ayrı iştir ve ikincisi sessizce ölür — çünkü başarısızlığı kimseye
görünmez, sadece **bir şeyin yokluğu** olarak tezahür eder.

**Kurallar:**
- Dış protokole giden metinde **dinamik alan asla ham gitmez**; kaçış şablonun
  içinde olur, çağıranın nezaketine bırakılmaz.
- Toplu gönderimde her öğe **bağımsız** denenir; biri patlayınca parti ölmez.
- Durum/defter yazımı gönderim hatasından **sonra da** çalışmalı (`finally`
  mantığı): arıza kaydı, arızanın kendisine kurban edilemez.
- Gönderilemeyen bir mesajın "gönderildi" damgası **geri alınır**, yoksa soğuma
  onu kalıcı olarak susturur.
- **Yokluk alarm üretmeli.** Bir şeyin gelmemesi, gelmesi kadar ölçülebilir
  olmalı: ardışık hata sayacı tut ve kullanıcının GÖRDÜĞÜ yere bas.
- `continue-on-error: true` kullanıyorsan hatayı **başka bir kanaldan** görünür
  kıl; yoksa o bayrak "sessizce boz" demektir.

**Ek (aynı gün, üretimde yakalandı):** Bu dersin düzeltmesi de aynı hataya düştü.
Görünürlük katmanının arıza defteri `apply_cooldown` state'i sıfırdan kurduğu için
her sessiz koşumda siliniyordu — uyarı bir koşum görünüp kayboluyordu. Yazdığım
test `saglik_guncelle`'yi DOĞRUDAN çağırıyordu, boru hattını görmüyordu; saf
fonksiyon doğru, **bağlantı** yanlıştı. Dersin kendisi kanıtladı: bir korumayı
sadece birim testiyle doğrulamak, onu doğrulamamaktır. **Testi mutlaka
üretimdeki çağrı zincirinden geçir.**

**Genel kural:** *"Sistem çalışıyor" ile "sistem konuşuyor" aynı şey değildir.
İkincisini ölçmüyorsan, birincisini de bilmiyorsun demektir.*

---

## L-017 — 2026-07-29 — AÇIK olan kolu ölçmeyi unutma: kapalı kola bakarken açık kol denetimsiz kaldı

**Olay:** Aday taraması 14 adayı tarayıp "hiçbiri eşiği geçemedi" hükmünü
veriyordu ve bu hüküm doğruydu — ama yalnız **taktik** (SAT) kolunun eşiğine
göre. Taktik kol `aktif: false` ile **kapalıydı**. Üretimde her gün hüküm üreten
kol **çekirdek**ti ve onun eşiği daha düşüktü (+1.99p vs +3.18p, makas ödenmez).
Yani proje aylardır kapalı kolu titizlikle denetleyip, açık kolu hiç ölçmemişti.
Ölçüldüğünde çıkan sonuç: çekirdek kolun her iki kademesi de kendi eşiğinin
ALTINDA (+1.34p ve −1.06p).

**Neden gözden kaçtı:** Dikkat riskin BÜYÜĞÜNE gitmişti — SAT gerçek para yakar,
kademe yalnız alımı yavaşlatır. Ama "küçük risk" ile "ölçülmemiş" aynı şey değil;
küçük etkiler de yanlış işaretli olabilir.

**Kural:** Bir eşik/hüküm raporu yazarken önce sor: **"bu rapor ŞU AN AÇIK olan
kolu ölçüyor mu?"** Birden fazla kol/mod varsa her biri kendi eşiğine göre
raporlanır; tek eşikli bir tablo, diğer kolun okuyucusunu yanıltır. Bir aday
bir kolda ❌ görünüp diğerinde ✅ olabilir — sütun tek ise bu bilgi kaybolur.

---

## L-016 — 2026-07-29 — Mutasyon yakalanmadıysa suçlu sentetik veridir: vacuous test sessizce geçer

**Olay:** `cekirdek_gecti` bayrağını sabit `False` yapan mutasyon 55 testin
hepsinden geçti. Sebep iki katmanlıydı: (1) eşik testleri elle yazılmış fixture
üzerinden çalışıyordu, üreticiye hiç dokunmuyordu (L-012'nin tekrarı); (2)
üreticiyi çağıran uçtan uca test ise **düz üstel** sentetik seri kullanıyordu ve
o seride her adayın tabana farkı özdeş **0.00** çıkıyordu — yani bayrak zaten
hiçbir zaman `True` olmuyordu. Test "geçiyordu" çünkü ölçecek bir şey yoktu.

**Ders:** Sentetik veri, korumanın tetiklendiği durumu ÜRETMİYORSA test vacuous
olur ve mutasyonu yakalayamaz. Düzgün/monoton sentetik seriler bu tuzağın en sık
kaynağıdır: gerçek hayatta ayrışan büyüklükler orada özdeş çıkar.

**Kural:** Bir bayrağı/eşiği test ederken **testin kendisi "kurgu gerçekten
tetikledi mi"yi assert etsin**:
```python
gecmesi_gereken = [a for a in adaylar if a["fark_puan"] > esik]
assert gecmesi_gereken, "kurgu eşiği aşan aday üretmedi; test vacuous olurdu"
```
Bu assert olmadan yeşil bir test, korumanın çalıştığını değil yalnızca
çökmediğini gösterir. Sentetik veriyi **rejimli** kur (bkz. `_doldur_rejimli`):
en az iki farklı davranış bölgesi olsun.

---

## L-015 — 2026-07-27 — Test yazmak yetmez: testin DÜŞEBİLDİĞİNİ kanıtla

**Olay:** Regresyon zırhı için 491 yeni test yazıldı ve hepsi ilk koşumda yeşil
geçti. Bu hiçbir şey kanıtlamıyordu — L-012 zaten "yeşil kalarak yanlış güven
veren test" vakasıydı. Bu yüzden 20 kontrollü **mutasyon** uygulandı: `asof`
filtresini `<`→`<=` yap, `drop_weekend_bars`'ı kaldır, `taktik.aktif: true` yap,
z kapısını 60→20 düşür, bir tabloyu `dbdump._TABLES`'tan düşür, `predictions.id`'yi
dump'tan çıkar, `feature_vector`'ın parametre sırasını değiştir, `karar.py`'ye
`import requests` ekle, kritik adım etiketini kaydır, eşiği koda göm, gram
carry'yi orandan TL farkına çevir... Her mutasyon `try/finally` ile geri alındı.
**20/20 yakalandı** — ancak bundan sonra "bu testler koruyor" cümlesi ölçüme
dayandı.

**Ders:** Bir testin değeri geçmesinde değil, **doğru durumda düşmesinde**dir.
"Testi yazdım, geçiyor" ifadesi ölçüm değil temennidir; mutasyon denetimi o
temenniyi 10 dakikada ölçüme çevirir.

**Kural:** Bir KİLİT koruma testi yazdığında korumayı bilerek boz, testin
düştüğünü gör, `finally` ile geri al. Düşmüyorsa test yanlış şeyi ölçüyordur.
Bu adım "kilit test" etiketi taşıyan her test için zorunludur; toplu koşum
`git status`'ün temiz kaldığını da doğrulamalı.

---

## L-014 — 2026-07-27 — Korumanın KAPSAMI da denetlenir: kilidi takıp kapıyı açık bırakma

**Olay:** `trg_predictions_immutable` "tahmin kaydı değiştirilemez" garantisinin
tamamıydı (ADR #007-F) ve gerçekten çalışıyordu — ama yalnız **UPDATE** için.
`DELETE` tamamen serbestti; oysa karneyi güzelleştirmenin en kısa yolu kötü
tahmini düzeltmek değil **silmek**tir. Ayrıca trigger'ın kolon listesinde
`kaynak` ve `model_version` yoktu: bir tahminin **hangi karneye sayıldığını** tam
olarak bu iki kolon belirliyor, yani tek satırlık bir `UPDATE` ile
`tahmin_backfill`'in 458 haftalık replay'i canlı karneye karıştırılabilirdi.

**Ders:** L-011 "koruma yazıldı ama bağlanmadı" diyordu; bu onun kardeşi:
koruma **bağlı ama kapsamı eksik**. Kısmi koruma, tam koruma sanıldığı için daha
tehlikelidir — kimse "acaba DELETE de kapalı mı?" diye sormaz.

**Kural:** Bir koruma yazınca üç soruyu sor: (1) hangi **fiiller** kapalı
(INSERT/UPDATE/DELETE)? (2) hangi **alanlar** kapalı — dışarıda kalan bir alan
kararı değiştirebiliyor mu? (3) test her fiil/alan için **ayrı ayrı** mı koşuyor?
Tek bir örnek üzerinden yazılmış test, listeye eklenmemiş alanı asla görmez —
bu yüzden kolon listesi testte de veri olarak durmalı (`KORUNAN_KOLONLAR`).

---

## L-013 — 2026-07-27 — Girdisini baştan okuyan iş, kısıtsız tabloda SAYAÇ üretir

**Olay:** `import_actions.import_all` her `daily_job` koşumunda TÜM arşiv
CSV'lerini baştan okuyor (dosya bazlı artımlılık yok) ve `db.insert_tick` düz
`INSERT` idi. `ticks` tablosunda benzersiz kısıt olmadığı için aynı gözlem her
gün yeniden yazılıyordu. Ölçüm: üretim dump'ında **15 999 tick satırı, tekil
olan 1 663** (9.6×); en eski satır **23 kez** yazılmıştı. İki zarar birden:
`data/altin.sql` her gün ~1663 satır büyüyordu (diff'lenebilir dump'ın var olma
sebebi olan repo şişmesi geri geliyordu) ve raporun "Ham tick: N" satırı veri
hacmini değil **koşum sayısını** ölçüyordu. `prim_history` ve `ohlc_1m`
PRIMARY KEY sayesinde etkilenmemişti — yani kusur tablonun tasarımındaydı,
iş akışında değil.

**Ders:** "Her koşumda baştan oku" basit ve dayanıklı bir tasarımdır **ama**
yazdığı her tabloda idempotentlik şart koşar. Kısıtsız bir tabloda bu desen,
ölçüm kılığında bir koşum sayacı üretir — L-010'un veri katmanındaki hâli.

**Kural:** Bir iş girdisinin tamamını yeniden okuyorsa, yazdığı her tablo için
sor: **"Aynı gözlem ikinci kez yazılırsa ne olur?"** Cevap "satır artar" ise ya
doğal anahtara `UNIQUE` + `INSERT OR IGNORE` koy, ya da artımlılığı kanıtla.
Denetimi tek sorguyla yapılır: `COUNT(*) == COUNT(DISTINCT <doğal anahtar>)`.
Kısıtı sonradan eklerken **mevcut kopyaları önce temizle** (indeks aksi halde
kurulamaz) ve eski dump'ların hâlâ yüklenebildiğini doğrula.

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
