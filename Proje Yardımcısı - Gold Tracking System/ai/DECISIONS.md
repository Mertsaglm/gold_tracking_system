# DECISIONS.md — Karar Günlüğü (ADR)

> Yalnızca ÖNEMLİ kararlar: mimari, araç, yaklaşım seçimleri.
> Her karar "neden"i ve "tekrar gözden geçirme koşulu" ile kaydedilir.
> En yeni karar en üste.

---

## #005 — 2026-08-28 — Çelişen denetim raporlarında konsensüs ARAMA; ayırt eden ölçümü koş

**Bağlam:** Altın projesi için iki bağımsız denetim raporu üretildi (Claude + GPT,
aynı gün, aynı commit). Aynı olguyu — bir metriğin varyansının çökmesini — **zıt**
okudular: biri *"düzeltme çalıştı, bu seri korunmalı"*, öbürü *"metrik öldü"*.
İkisi de kendi içinde tutarlı, gerekçeli ve ikna ediciydi.

**Seçenekler:**
- A) Ortak noktaları al, çelişenleri "belirsiz" diye bırak → *konsensüs*
- B) Daha ayrıntılı/güvenilir görünen rapora ağırlık ver → *yazara güven*
- C) İki raporun **öngörüsünü ayıran** bir ölçüm tasarla ve koş

**Karar:** **C.** Çelişki bir oylama sorusu değil, bir ölçüm sorusudur.

**Neden:** Bu vakada A ve B'nin ikisi de **yanlış cevabı** verirdi:
- A (konsensüs): iki rapor da *"kaynak düzeltmesi yerindeydi"* öncülünü
  **paylaşıyordu**. Ortak öncül doğrulanmamıştı ve asıl hata oradaydı. Konsensüs,
  paylaşılan bir yanlışı görünmez kılar.
- B (yazara güven): daha ayrıntılı olan rapor bu noktada haklıydı ama bunu
  *ayrıntısı* değil ölçümü kanıtladı. Ayrıntı, doğruluğun vekili değildir.

Ayırt eden ölçüm tek satırlık bir soruydu: *"metrik formülünde şu terim
sadeleşiyor mu?"* — cebirle soruldu, 934 kayıtla doğrulandı, tek turda bitti.
Vekil değişken düzeltme sonrası varyansın **%99.81'ini**, öncesinde **%18.2'sini**
açıklıyordu. Çelişki kapandı.

**Genel kural (Usta bunu uygular):** İki kaynak (rapor, model, araç, insan) aynı
olguyu zıt okuduğunda:
1. **Ortak öncülü ara.** Çelişkinin altında ikisinin de sorgulamadığı bir
   varsayım genellikle vardır; asıl hata orada olur.
2. **Ayırt eden öngörüyü yaz.** "A doğruysa X görürüm, B doğruysa Y" —
   yazılamıyorsa çelişki henüz ölçülebilir hâle gelmemiştir.
3. **Ölç, sonra hüküm ver.** "İkisinde de haklılık payı var" bir sonuç değil,
   ölçümden kaçmaktır.

**Ayrıca:** Bir raporun ÖNERDİĞİ çözüm, bulgusu doğru olsa bile bayat olabilir.
Aynı turda bir rapor "gölge kol" önerdi; o çözüm 17 gün önce **ölçülüp
reddedilmişti** (proje ADR #012-B). Bulgu ile çözüm ayrı ayrı denetlenir.

**Tekrar gözden geçir:** Ayırt edici ölçümün tasarlanamadığı bir çelişki
çıkarsa — o zaman "karar veremedim" yazmak, taraf tutmaktan iyidir.

---

## #004 — 2026-07-27 — Usta'nın koruma disiplini: testin DÜŞTÜĞÜNÜ kanıtlama zorunluluğu

**Bağlam:** Altın projesinde 491 koruma testi yazıldı ve hepsi ilk koşumda yeşil
geçti. Ama L-012 zaten "yeşil kalarak yanlış güven veren test" vakasıydı: bir
fixture üreticiden sapmıştı ve ona dayanan testler gerçekliğini yitirmişti.
Yani **"test yazdım, geçiyor" cümlesi bu sistemde bir kanıt değildi** — oysa
Usta'nın tüm iş çıktısı bu cümleyle teslim ediliyordu.

Ayrıca aynı turda iki gerçek açık, mevcut testlerin **kapsamı** yüzünden
görünmemişti: bir değiştirilemezlik trigger'ı UPDATE'i engelliyor ama DELETE'i
bırakıyordu ve tek bir örnek üzerinden yazılmış test bunu göremiyordu.

**Seçenekler:**
- A) Bir şey yapma; kod inceleme yeterli olsun → L-012 zaten bunun olmadığını gösterdi
- B) Kapsam ölçüm aracı (coverage) zorunlu kıl → satır kapsaması "test doğru
  şeyi ölçüyor mu" sorusunu **cevaplamaz**; yeşil kapsama yanlış güven verir
- C) **Mutasyon disiplini:** korumayı bilerek boz, testin düştüğünü gör, geri al

**Karar:** C. `AGENTS.md §5`'e **"Koruma disiplini — testin DÜŞTÜĞÜNÜ kanıtla"**
alt bölümü eklendi: (1) korumayı boz → testi koş → düştüğünü gör → `finally` ile
geri al, (2) düşmüyorsa **testi** düzelt (korumayı değil), (3) toplu koşumdan
sonra çalışma alanının temiz kaldığını doğrula. Ek olarak iki soru kurallaştı:
"bu korumayı atlayan bir yol var mı?" ve "hangi fiiller/alanlar kapsam dışında?"

**Neden:** Ölçüm kültürünün (`§5` İddia denetimi) testlere uygulanmış hâli.
Bu proje bir iddiayı ham tabana karşı ölçmeden kabul etmiyor; "testlerim
koruyor" da bir iddiadır ve ölçülebilir — üstelik 10 dakikada. İlk uygulamada
20 mutasyonun 20'si yakalandı, yani disiplin uygulanabilir olduğunu da gösterdi.

**Neden coverage değil:** Kapsama "satır çalıştı mı" der; mutasyon "yanlış olsa
fark eder miydik" der. Aranan ikincisi.

**Tekrar gözden geçir:** Mutasyon adımı elle yapılıyor (script + `try/finally`).
Sık tekrarlanan bir işe dönüşürse küçük bir `scripts/mutasyon.py` yazılabilir —
ama YAGNI: iki turda bir kullanılan bir şey için araç yazma.

---

## #003 — 2026-07-27 — LESSONS numara uzayı ORTAK; kök ayrıntılı, paket genelleştirilmiş

**Bağlam:** Ders dosyası iki yerde yaşıyor: proje kökünde (`ai/LESSONS.md` —
IDE'lerin okuduğu) ve devir paketinde (taşınabilir tohum). Bir denetimde kökteki
iki dersin **ikisinin de L-002 numaralı** olduğu görüldü; düzeltilirken yalnız
köke bakılıp bir sonraki boş numara "L-005" sanıldı. Oysa pakette L-005 zaten
`.gitignore` dersiydi → **iki farklı ders, aynı numara.** Belirsizlik çözülürken
başka bir belirsizlik üretildi. Ayrıca kök dosyada L-005…L-008 hiç yoktu, yani
kodda verilen bir `L-008` atfı boşluğa gidiyordu.

**Seçenekler:**
- A) Tek dosyaya indir (paketi kaldır) → basit ama devir/tohumlama işlevi ölür
- B) Ayrı numara uzayları (`P-001` paket, `L-001` kök) → çakışma imkânsız ama
  aynı ders iki isimle anılır, atıflar okunmaz hale gelir
- C) **Ortak numara uzayı + iki dosyada da tam set** → aynı ders aynı numara;
  kök proje ayrıntısını, paket genelleştirilmiş hâlini tutar

**Karar:** C. Her iki dosya da **L-serisinin tamamını** içerir. Aynı numara
= aynı ders; kökteki sürüm somut (tarih, sayı, dosya adı), paketteki sürüm
taşınabilir (proje adı geçmez). Yeni ders eklerken **iki dosyadaki en büyük
numaraya** bakılır. Kural her iki dosyanın başına uyarı olarak yazıldı.

**Neden:** Atıflar (`bkz. L-008`) ancak numara tekse anlamlıdır — ve kod
yorumlarında, ADR'lerde, STATE'te bu atıflar kullanılıyor. Ayrı uzay (B) atıfları
okunamaz kılardı; tek dosya (A) paketin varlık sebebini yok ederdi.

**Kontrol:**
```
grep -h '^## L-' ai/LESSONS.md 'Proje Yardımcısı'*/ai/LESSONS.md | sort | uniq -c
```
Her numara **tam 2 kez** görünmeli. Tek görünen = bir dosyada eksik.

**Tekrar gözden geçir:** Paket ikinci bir projeye tohumlandığında, o projenin
kendi dersleri numara uzayını çatallaştırır (iki proje aynı anda L-013 yazabilir).
O gün geldiğinde ya proje öneki (`GOLD-L-013`) ya da paketin merkezi kalması
kararlaştırılmalı.

---

## #002 — 2026-07-24 — Köprüler proje KÖKÜNDE + Kiro desteği + commit onay kuralı

**Bağlam:** Şablon bir projeye (altın takip) uygulandı ve sahada üç eksik çıktı:
(1) dosyalar alt klasöre kopyalanınca hiçbir IDE okumadı — sistem sessizce atıl
kaldı; (2) Mert'in kullandığı **Kiro** için köprü yoktu; (3) asistan kendi
kararıyla commit/push atınca Mert müdahale etti.

**Karar:**
- Kanonik `AGENTS.md` + tüm köprüler **daima proje kökünde**. `yeni-proje.sh`
  bunu zaten yapıyordu; README'ye uyarı olarak yazıldı.
- `.kiro/steering/usta.md` köprüsü eklendi (`inclusion: always`), `yeni-proje.sh`
  artık onu da kopyalıyor. Kapsanan araçlar: Codex, Antigravity, GLM, Kiro,
  VSCode, Claude Code, Cursor.
- `AGENTS.md §10`'a **`git commit`/`push` daima onaya tabidir** kuralı eklendi;
  untracked dosya silmek de onaya bağlandı (geri alınamaz).

**Neden:** Yanlış yerdeki kural dosyası = yok hükmünde (bkz. LESSONS L-004).
Araç listesi Mert'in gerçek kullanımına göre olmalı, varsayıma göre değil.
Repoya ne gideceğine kullanıcı karar verir — asistan önerir.

**Tekrar gözden geçir:** Yeni bir IDE farklı bir konvansiyon dayatırsa köprü
ekle; bir araç AGENTS.md desteğini bırakırsa o köprüyü güncelle.

---

## #001 — 2026-07-23 — Taşınabilirlik için AGENTS.md standardı + düz markdown hafıza

**Bağlam:** Claude Code aboneliği bitince Cursor, Antigravity, VS Code gibi
farklı araçlara geçilecek. Usta sistemi her araçta aynı şekilde çalışmalı.

**Seçenekler:**
- A) Araca özel özellikler (.claude/commands, .cursorrules...) → güçlü ama her araçta yeniden kurulum gerekir
- B) Tek AGENTS.md + düz markdown hafıza dosyaları → her uyumlu araç okur, kilitlenme yok
- C) Fine-tuning / özel model → pahalı ve gereksiz; sorun davranış+bağlam sorunu, bilgi sorunu değil

**Karar:** B. AGENTS.md kanonik dosya; CLAUDE.md, GEMINI.md ve
copilot-instructions.md yalnızca ona işaret eden köprüler. Komutlar araç
özelliği değil, AGENTS.md içinde "sözleşme" olarak tanımlı.

**Neden:** AGENTS.md araçlar arası fiili standart (Claude Code, Cursor,
Antigravity, Copilot, Codex destekliyor). Düz markdown hiçbir araca bağımlı
değil; git ile taşınır, her yerde okunur.

**Tekrar gözden geçir:** Ana kullanılan araç AGENTS.md desteğini bırakırsa
veya araca özel bir özellik (ör. gerçek slash komutları) ciddi verim farkı
yaratmaya başlarsa.

---

<!-- Yeni karar şablonu:

## #NNN — YYYY-MM-DD — Kısa başlık

**Bağlam:** Hangi sorun/ihtiyaç bu kararı doğurdu?

**Seçenekler:**
- A) ... → artı/eksi
- B) ... → artı/eksi

**Karar:** Seçilen şey.

**Neden:** Hangi kısıta/hedefe dayanarak?

**Tekrar gözden geçir:** Hangi koşul oluşursa bu karar masaya geri gelir?
-->
