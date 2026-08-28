# Proje Yardımcısı — Gold Tracking System

Bu klasör, **Altın Takip Sistemi** projesinin AI yardımcı ("Usta") **devir
paketidir**. İki işi vardır:

1. **Devir/taşıma:** Claude Code aboneliği bitip Codex, Antigravity, GLM, VSCode
   gibi başka bir araca geçildiğinde, Usta'nın kimliği ve bu projede öğrenilen her
   şey burada toplu ve taşınabilir halde durur.
2. **Yeni proje tohumu:** `yeni-proje.sh` ile bu birikim yeni bir projeye
   kopyalanır — kurallar ve dersler sıfırdan yazılmaz.

> **Bu klasör canlı sistem DEĞİLDİR.** IDE'ler proje **kökündeki** dosyaları okur.
> Burası kararlı (nadiren değişen) içeriği tutar; günlük durum kökte yaşar.

---

## ⚠️ En önemli kural: kök kanoniktir

| Nerede | Ne | Kim okur |
|---|---|---|
| **Proje kökü** (`../AGENTS.md`, `../ai/`) | **CANLI** kurallar + proje hafızası | IDE'ler otomatik okur |
| **Bu klasör** | Devir paketi + yeni proje tohumu | Kimse otomatik okumaz |

Hiçbir IDE alt klasördeki kural dosyasını otomatik okumaz (bkz. `ai/LESSONS.md`
→ **L-004**). Buradaki dosyalar **kopya/tohumdur**; bir kuralı değiştireceksen
**önce kökteki `AGENTS.md`'yi** değiştir, sonra buraya yansıt.

**Canlı durumu buradan okuma:** "nerede kaldık, sırada ne var, ne zaman ne
yapılacak" sorularının cevabı daima **`../ai/STATE.md`**'dedir (TAKVİM tablosu
orada). Buradaki `ai/STATE.md` yalnızca yön levhası + tarihli özettir.

**👤 SENDE KALANLAR neden burada değil?** Mert'in yapması gereken işlerin listesi
(kararlar, onaylar, dışarıdan doğrulamalar) `../ai/STATE.md` → TAKVİM tablosunda
`Kim=👤` satırları olarak durur ve `AGENTS.md §2` Usta'yı **her oturum başında
tarihi gelmiş satırları sormaya** zorlar. Buraya konsaydı hiçbir IDE okumazdı ve
hatırlatma hiç çalışmazdı — **L-004'ün ta kendisi.**

---

## İçindekiler

```
AGENTS.md                         ← KANONİK kurallar (kökle birebir aynı olmalı)
CLAUDE.md                         ← Claude Code / GLM köprüsü
GEMINI.md                         ← Antigravity köprüsü
.github/copilot-instructions.md   ← VS Code (Copilot) köprüsü
ai/
  PROJECT.md        ← Altın projesinin kimliği (kararlı — nadiren değişir)
  PROJE-GUNLUGU.md  ← **Ne inşa edildi, ne ölçüldü, hangi iddia çürüdü, sınırlar ne**
                       (devralanın okuyacağı ana anlatı — Faz 8 + iki denetim turu)
  PROFILE.md        ← Mert'in profili (PROJELER ARASI ortak, kişisel → gitignore'da)
  LESSONS.md        ← Sahadan çıkan dersler L-001…L-020 (PROJELER ARASI taşınır;
                       numara uzayı kökle ORTAK — bkz. DECISIONS.md #003)
  DECISIONS.md      ← Yardımcı SİSTEMİNİN kararları (projenin kararları kökte)
  STATE.md          ← Yön levhası + tarihli özet (canlı durum kökte)
  archive/
yeni-proje.sh                     ← Bu birikimi yeni bir projeye kopyalar
```

> `PROJE-GUNLUGU.md` **yalnız geçmişi** anlatır (geçmiş değişmez → kararlı).
> "Sırada ne var" oraya YAZILMAZ; tek kaynak `../ai/STATE.md`'dir.

**Neden bazı dosyalar burada, bazıları kökte?** Ayrım **değişme hızına** göre:
kararlı olanlar (kurallar, kimlik, profil, dersler) taşınabilirlik için burada da
durur; her oturum değişenler (STATE, proje kararları) yalnız kökte yaşar —
ikizlenirse kaçınılmaz olarak ayrışır.

---

## Araç uyumluluğu

Mert'in kullandığı araçlar: **Codex, Antigravity, GLM, VSCode** (+ Claude Code, Cursor).

| Araç | Okuduğu dosya (PROJE KÖKÜNDE) |
|---|---|
| Codex / Cursor | `AGENTS.md` |
| Claude Code / GLM | `CLAUDE.md` → AGENTS.md |
| Antigravity | `GEMINI.md` → AGENTS.md |
| VS Code (Copilot) | `.github/copilot-instructions.md` → AGENTS.md |

Kiro köprüsü (`.kiro/steering/`) **bilinçli olarak kaldırıldı** (2026-07-25) —
Kiro az kullanılıyor, diğer köprüler yeterli. Gerekirse AGENTS.md'ye yönlendiren
3 satırlık bir `.kiro/steering/usta.md` ile geri eklenir.

Okumayan bir araçta son çare: sohbetin ilk mesajına
**"AGENTS.md'yi oku ve oradaki kurallara göre çalış"** yaz.

Komutlar: `/durum` · `/baslat` · `/tanis` · `/karar` · `/plan` · `/kapat` ·
`/ders` · `/ogret` (araç özelliği değil, AGENTS.md'de tanımlı sözleşme).

---

## Başka bir araca geçerken (devir kılavuzu)

1. Projeyi yeni araçta aç; araç kök `AGENTS.md`'yi (veya köprüsünü) okumalı.
2. Sohbete **`/durum`** yaz. Usta `../ai/STATE.md`'yi okuyup özetliyorsa sistem
   devrede demektir — dosyaların yerinde durduğunu görmek yeterli değildir (L-004).
3. Özet gelmiyorsa "AGENTS.md'yi oku ve uygula" yazarak zorla; o araç için köprü
   dosyası yoksa AGENTS.md'ye yönlendiren yeni bir köprü ekle.
4. `../ai/STATE.md` → **TAKVİM** tablosundan o günkü işi bul.

---

## Yeni bir projeye tohumlarken

```bash
./yeni-proje.sh ~/Desktop/YeniProjem
```

Kurallar + profil + dersler kopyalanır; `PROJECT.md` boş, `STATE.md` sıfırdan
başlar. Sonra yeni projede `/baslat` yaz — Usta proje keşfini kendisi yapar.

### Kurulumda atlanmaması gerekenler

1. **Public repo ise `ai/PROFILE.md`'yi gitignore'a al** (kişisel içerik).
   `.gitignore` **satır-sonu yorumu desteklemez** — yorumu kendi satırına yaz,
   yoksa kural sessizce çalışmaz (L-005). Sonra doğrula:
   `git check-ignore -q ai/PROFILE.md && echo korunuyor`
2. **Klasör adını değiştirirsen gitignore satırını da güncelle.** Bu klasörün adı
   bir kez değişti (`Proje Yardımcısı` → `Proje Yardımcısı - Gold Tracking System`)
   ve eski kural tutmayınca kişisel profil açıkta kaldı — 2026-07-25'te fark edilip
   kapatıldı.
3. **Kuralların gerçekten yüklendiğini `/durum` ile test et** (L-004).
