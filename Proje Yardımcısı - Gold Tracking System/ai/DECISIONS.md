# DECISIONS.md — Karar Günlüğü (ADR)

> Yalnızca ÖNEMLİ kararlar: mimari, araç, yaklaşım seçimleri.
> Her karar "neden"i ve "tekrar gözden geçirme koşulu" ile kaydedilir.
> En yeni karar en üste.

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

**Karar:** C. Her iki dosya da **L-001…L-012'nin tamamını** içerir. Aynı numara
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
