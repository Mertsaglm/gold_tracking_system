# DECISIONS.md — Karar Günlüğü (ADR)

> Yalnızca ÖNEMLİ kararlar: mimari, araç, yaklaşım seçimleri.
> Her karar "neden"i ve "tekrar gözden geçirme koşulu" ile kaydedilir.
> En yeni karar en üste.

---

## #003 — 2026-07-24 — Veri kapsaması: platform kısıtını kabul et, veri kalitesini iyileştir

**Bağlam:** Raporlar "kapsama %62" gösteriyordu. Ölçüm (17 gün, 231 kayıt):
GitHub Actions `*/15` cron'unu gerçekte medyan ~94 dk'da çalıştırıyor (6 kat seyrek) —
throttling. Ayrı olarak kayıtların ~%7'si truncgil transient hatasından geçersiz
(gram/çeyrek boş; yfinance/ons hep dolu).

**Seçenekler:**
- A) Dış cron servisi → `workflow_dispatch` ile ~15 dk garanti → zamanlamayı düzeltir
  AMA dış bağımlılık + GitHub PAT'i 3. tarafta (güvenlik yüzeyi); "ayrı sunucu/servis
  yok" kısıtına aykırı
- B) Tur-içi çoklu örnekleme → kayıt sayısını şişirir ama kapsama metriğini
  anlamsızlaştırır (kümelenmiş örnek; 90 dk kör nokta durur) — metriği kandırır
- C) Platform kısıtını KABUL et (~90 dk kişisel monitör için yeterli — YAGNI) +
  gerçek ücretsiz kazanç olan VERİ KALİTESİNİ iyileştir: kaynak retry

**Karar:** C. GitHub cron throttling ücretsiz düzeltilemez ve ~90 dk bu kullanım için
yeterli. `archive_fetch`'e kaynak-retry eklendi (`sources.fetch_retries=3`,
`fetch_retry_backoff_s=4`) → %7 geçersiz kayıt düşer. Kapsama metriği dürüst
bırakıldı (şişirilmedi). Dış altyapı reddedildi.

**Neden:** Mert'in kısıtı ücretsiz + ayrı sunucu yok + basit. Retry hepsini karşılar;
dış cron+PAT karşılamaz. Metriği şişirmek [[ölçüm kültürü]]ne aykırı.

**Tekrar gözden geçir:** Sub-90-dk anomali tespiti kanıtlanmış ihtiyaç olursa
(gün-içi sert hareketler kaçırılıyorsa) dış tetikleyici (A) yeniden masada.

---

## #002 — 2026-07-24 — Usta sistemi proje köküne + tüm IDE köprüleri

**Bağlam:** Claude Code aboneliği bitince altın projesi Codex, Antigravity, GLM,
Kiro, VSCode gibi farklı araç+modellerle geliştirilecek. Usta sistemi bir alt
klasördeydi (`Proje Yardımcısı/`) — hiçbir IDE alt klasördeki kural dosyasını
otomatik okumaz, sistem atıldı.

**Seçenekler:**
- A) Alt klasörde tut, kökten köprü ver → kırılgan; relative path'ler bozulur,
  Kiro steering redirect'i güvenilmez
- B) Sistemi proje KÖKÜNE taşı (`yeni-proje.sh`'in kendi tasarımı) → her araç
  kökten okur
- C) Her araç için elle ayrı config → bakım zor, drift riski

**Karar:** B. Kök kanonik `AGENTS.md` + `ai/` hafıza; `CLAUDE.md`, `GEMINI.md`,
`.github/copilot-instructions.md` ve `.kiro/steering/usta.md` yalnızca AGENTS.md'ye
işaret eden köprüler. Codex/Cursor/GLM: AGENTS.md (GLM Claude-uyumlu istemcide
CLAUDE.md); Kiro: `.kiro/steering`; VSCode: copilot-instructions.

**Neden:** Alt klasör = atıl sistem. Kök yerleşim, şablonun kendi script'inin
yaptığı şey ve tek gerçekten evrensel konum. Düz markdown → araç kilidi yok.

**Tekrar gözden geçir:** Bir araç AGENTS.md/steering desteğini bırakır veya yeni
bir araç farklı bir konvansiyon dayatırsa köprü ekle/güncelle.

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
