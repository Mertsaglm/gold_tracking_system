# STATE.md — Yön levhası (canlı durum burada DEĞİL)

> ⚠️ **Bu dosya canlı durum tutmaz.** "Nerede kaldık, sırada ne var, ne zaman ne
> yapılacak" sorularının cevabı **`../../ai/STATE.md`**'dedir — TAKVİM tablosu orada.
>
> Neden ikizlenmiyor: STATE her oturumda değişir. İki kopya tutulursa kaçınılmaz
> olarak ayrışır ve hangisinin doğru olduğu belirsizleşir (aynı tuzağın kod
> tarafındaki örneği: LESSONS **L-008**, eşik mantığının iki yerde ayrışması).
>
> Burada yalnızca **devir paketinin kendi durumu** ve tarihli bir özet durur.

**Son güncelleme:** 2026-07-27

---

## Nereye bakmalı

| Soru | Dosya |
|---|---|
| Nerede kaldık? Sırada ne var? Ne zaman ne yapılacak? | **`../../ai/STATE.md`** (TAKVİM) |
| **Benim (Mert'in) yapmam gereken ne var, tarihi geldi mi?** | **`../../ai/STATE.md`** → TAKVİM'de `Kim=👤` satırları. Usta bunları `AGENTS.md §2` gereği her oturum başında SORMAK ZORUNDA |
| Ne inşa edildi, ne ölçüldü, hangi iddia çürüdü, sınırlar ne? | **`PROJE-GUNLUGU.md`** (burada) |
| Proje nedir, kapsamı/kısıtları ne? | `PROJECT.md` (burada) veya `../../ai/PROJECT.md` |
| Bu karar neden böyle alındı? | `../../ai/DECISIONS.md` (proje) · `DECISIONS.md` (yardımcı sistemi) |
| Hangi tuzağa bir daha düşmeyelim? | `LESSONS.md` (L-001…L-015) — numara uzayı kökle ORTAK, bkz. `DECISIONS.md` #003 |
| İnşa döneminde ne ölçüldü, hangi iddia çürütüldü? | `../../docs/TESLIMAT-ARSIV.md` |
| Haftalık 5 dakikalık kontrol nasıl yapılır? | `../../İZLEME.md` |

---

## Devir paketinin durumu

**Aktif milestone:** Paket sahada doğrulandı; altın projesine göre dolduruldu.

### ✅ Tamamlananlar
- 2026-07-23 — Usta sistemi kuruldu (AGENTS.md + `ai/` hafıza katmanı + IDE köprüleri)
- 2026-07-24 — İlk gerçek projede (altın takip) sahaya alındı; eksikler giderildi:
  kök yerleşim şartı, `AGENTS.md §10` commit/push onay kuralı, PROFILE dolduruldu,
  ilk 4 ders işlendi
- 2026-07-25 — İkinci tur geri besleme: `AGENTS.md §5` **İddia denetimi** protokolü,
  `§6` **TAKVİM tutma kuralı**, dersler L-005…L-008, README "kurulumda atlanmaması
  gerekenler"
- 2026-07-25 — **Paket altın projesine göre dolduruldu:** klasör
  `Proje Yardımcısı - Gold Tracking System` olarak yeniden adlandırıldı;
  `PROJECT.md` altın projesinin kimliğiyle dolduruldu; README devir kılavuzu
  haline getirildi; bu dosya yön levhasına çevrildi (ikizlenme önlendi);
  Kiro köprüsü kaldırıldı (az kullanılıyor)
- 2026-07-27 — **Uçtan uca denetim paketi besledi (4 yeni ders + 1 ADR).**
  Altın projesinde karar motoru push öncesi denetlendi; çıkan dersler
  genelleştirilip buraya işlendi:
  **L-009** türetilmiş dosya ↔ izlenmeyen kaynak senkronu ·
  **L-010** tek değerden başkasını üretemeyen "ölçüm" kimliktir (denetimin en
  değerli bulgusu: bir karne metriği piyasa ne yaparsa yapsın 0.00 çıkıyordu ve
  bir kapının şartı ona bağlıydı) ·
  **L-011** yazılmış ama bağlanmamış koruma = olmayan koruma ·
  **L-012** fixture üreticiden türemiyorsa test mock'u doğrular.
  `DECISIONS.md #003`: LESSONS numara uzayı kök ile ORTAK (çakışma yaşandı,
  kural yazıldı). `PROJECT.md` karar motoru gerçeğine göre tazelendi
  (amaç fonksiyonu = terminal gram; karnenin ölçüm üretememesi açık nokta).
- 2026-07-27 — **`PROJE-GUNLUGU.md` eklendi + 👤 SENDE KALANLAR mekanizması.**
  Devralanın okuyacağı ana anlatı: mimari, Faz 8'in tüm alt fazları, ölçüm
  tabloları, çürütülen 8 iddia, bugünün 8 bilinen sınırı, "ilk 30 dakika"
  kılavuzu. Ayrıca Mert'in kendi yapması gereken işler için kalıcı mekanizma
  kuruldu: kök `ai/STATE.md` TAKVİM tablosuna **Kim** (👤/🤖) ve **Durum**
  sütunları eklendi, `AGENTS.md §2`'ye "tarihi gelmiş 👤 satırlarını oturum
  başında SOR" kuralı yazıldı. Liste bilerek **köke** kondu — pakete konsaydı
  hiçbir IDE okumaz, hatırlatma hiç çalışmazdı (L-004).

- 2026-07-27 (2. tur) — **Regresyon zırhı paketi besledi (3 yeni ders + 1 ADR).**
  Altın projesine 491 test eklendi (299 → 800) ve testin kendisi 20 mutasyonla
  ölçüldü. Genelleştirilip buraya işlenenler: **L-013** girdisini baştan okuyan
  iş kısıtsız tabloda sayaç üretir · **L-014** korumanın KAPSAMI da denetlenir
  (kilidi takıp kapıyı açık bırakma) · **L-015** testin düşebildiğini kanıtla.
  `AGENTS.md §5`'e **"Koruma disiplini — testin DÜŞTÜĞÜNÜ kanıtla"** protokolü
  eklendi (`DECISIONS.md #004`); kök ↔ paket senkronu artık altın projesinde
  bir testle denetleniyor.

### 🧱 Bilinen kısıt
- **Kural değişikliği iki yere yazılmalı:** kanonik kopya proje kökündedir; buradaki
  `AGENTS.md` onun taşınabilir ikizidir. Değişiklik önce köke, sonra buraya.
  Senkron kontrolü: `diff ../../AGENTS.md AGENTS.md` → çıktı boş olmalı.
  (Altın projesinde bu kontrol otomatik:
  `tests/test_dokuman_tutarliligi.py::test_paketteki_agents_md_kokle_BIREBIR_ayni`.)

### 🎯 Sıradaki 3 İş (bu paket için)
1. Paketi ikinci bir projeye `./yeni-proje.sh` ile tohumla — **DoD:** yeni klasörde
   köprüler kökte, `/durum` çalışıyor
2. Yeni projede `PROJECT.md`'yi `/tanis` ile yeniden doldurt (buradaki içerik altın
   projesine ait) — **DoD:** yeni proje kimliği yazıldı ve onaylandı
3. Bir kural değişikliğinden sonra kök↔paket senkronunu doğrula — **DoD:**
   `diff` çıktısı boş

### 📦 Backlog
- `PROFILE.md`'de "öğrenmek istedikleri" ve "çalışma alışkanlıkları" boş — uygun
  bir anda sor, doldur
