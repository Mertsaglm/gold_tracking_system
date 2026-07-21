# TESLIMAT — Faz 5: Sertleştirme, Gizlilik, Repo Şişme Önlemi, İzleme Dönemi

Tarih: 2026-07-07 · **91/91 test geçti** (79 → +12) · Repo public

## Özet

| Bölüm | Durum |
|---|---|
| 0. Gizlilik temizliği (maskeleme) | ✅ chat_id/bot adı maskelendi + rapor/log savunma maskesi |
| 1. Bot komut yetkilendirmesi | ✅ chat_id beyaz liste + 4 test |
| 2. Repo şişme önlemi (SQL dump) | ✅ dump/restore, binary gitignore, **workflow uçtan uca doğrulandı** |
| 3. Hafta sonu canlı test hazırlığı | ✅ 5 dry-run test + rapor bölümü (sessiz-kalma dahil) |
| 4. İZLEME.md | ✅ haftalık checklist + duraklatma + veri konumları |
| 5. Teslimat | ✅ bu dosya |

---

## Bölüm 0 — Gizlilik (repo public kalıyor)

**Öncesi → Sonrası** (izlenen dosyalarda; ham değerler burada da kasıtlı olarak yazılmadı):
```
TESLIMAT.md:      "Bot: `<botun-gerçek-adı>` · chat_id `<10-haneli-id>`"
              →   "Bot: `<bot_adı>` · chat_id `<chat_id>`"
TESLIMAT-FAZ4.md: "chat <10-haneli-id>"  →  "chat <chat_id>"
```
- `git grep` ile izlenen `.md`'lerde artık **0 iz** (doğrulandı).
- `logs/*.log` (chat_id içeriyordu) **izlemeden çıkarıldı** (Faz 3'te gitignore edilmişti ama
  eski commit'lerden tracked kalmıştı).
- **Savunma katmanı:** `util.mask_pii()` rapor kaydında chat_id'yi maskeler; Telegram log'u artık
  chat_id'yi tam yazmıyor (son 3 hane).
- **Git geçmişi notu (gizlemeden):** eski commit'lerde chat_id hâlâ görünür. chat ID düşük riskli
  (bot'a mesaj atmak için token da gerekir; token secret'ta). Geçmiş yeniden yazma (`filter-repo`)
  **zahmete değmez** — bilinçli karar, gizlenmeden yazıldı.

## Bölüm 1 — Bot komut yetkilendirmesi

`telegram_bot.allowed_chats()` + `is_allowed()`: `.env TELEGRAM_CHAT_ID` + config
`extra_allowed_chat_ids`. Komut işleyicide izinsiz sohbet **sessizce yoksayılır + loglanır**
(son 3 hane). Bot açıkken botu bulan yabancı komut atamaz. **4 test**
(sahip izinli, yabancı engelli, ekstra izinli, int/str chat_id).

## Bölüm 2 — Repo şişme önlemi (yönetici denetim bulgusu)

**Sorun:** günlük job SQLite binary'sini commit'liyordu → git her sürümü tam saklar → yıllık
yüzlerce MB. **Ölçüm:** git geçmişindeki `data/altin.sqlite` = **5 sürüm, toplam 3252 KB**
(en büyük 844 KB). Küçük → geçmiş yeniden yazmaya değmez; ama trajectory kötü (her gün +~800KB).

**Çözüm:**
- `src/dbdump.py`: **deterministik SQL text dump** (`data/altin.sql`) — her tablo mantıksal
  anahtara göre sıralı → günlük diff yalnız yeni satırlar.
- `src/restore_db.py`: dump'tan SQLite'ı kurar.
- `data/altin.sqlite` **gitignore**'a alındı (binary izlenmiyor); `data/altin.sql` izleniyor.
- Workflow'lar güncellendi: **daily** = başta `restore_db` → iş → `dbdump` → dump commit;
  **archive** = notify öncesi `restore_db` (salt-okunur).

**Kanıtlar:**
1. Dump→restore round-trip: 8 tablo satır sayıları **birebir eşit** (ticks 193, evds_daily 7599,
   history_daily 2549, … → restore sonrası aynı).
2. **Gerçek Actions daily workflow** (yeni akışla) **conclusion=success**; commit'i:
   ```
   data/altin.sql              | 59 satır diff   ← binary 844KB yerine 59 satırlık text diff
   reports/rapor_2026-07-07.md
   (data/altin.sqlite YOK — gitignore ✓)
   ```
   Yani dump/restore uçtan uca çalışıyor ve günlük diff küçük.
3. **3 birim test** (round-trip eşitlik, determinizm/sıra, SQL kaçış O'Brien).
- CSV arşivleri append-only text — doğru, dokunulmadı.

## Bölüm 3 — İlk hafta sonu (11-13 Temmuz) hazırlığı

**5 dry-run test:**
- Cumartesi/Pazar forex kapalı (2026-07-11/12), Pazartesi açık → import weekend=1 yazacak.
- Cumartesi zamanında **anomali bildirimi bastırılıyor** (all_fresh=False → boş).
- **"Pazartesi beklentisi" günde en fazla 1** (24s soğuma, cap=1).
- Rapor **"Hafta Sonu Beklentisi vs Gerçekleşme"** bölümü: veri yokken **SESSİZ** (hafta içi
  yanlışlıkla görünmez); veri varken görünür.

Pazartesi 14 Temmuz raporu ilk kez bu bölümü içerecek — İZLEME.md'de kullanıcıya beklenti yazıldı.

## Test kırılımı (91)
```
calc(10) state_machine(16) indicators(9) evds_dates(7) backtest(15) signals(5)
calculators(7) trends(4) notify(10) authz(4) dbdump(3) weekend(5)   → 91 passed
```

## Bilinen / sonraki
- Git geçmişindeki eski chat_id ve 3.2MB DB blob'ları duruyor (bilinçli — rewrite'a değmez).
- İnteraktif bot komutları yerelde `src.telegram_bot` açıkken çalışır (Actions push-only).
- Z-skor arşivi doluyor; ~60. günde bildirimleri açılır.

---

## Durum: inşa dönemi kapandı, izleme dönemi başladı.

Sistem GitHub Actions'ta otonom çalışıyor: 15 dk arşiv+bildirim, günlük rapor, hafta sonu mantığı,
pazartesi mutabakatı, haftalık özet. Kullanıcı sadece izliyor (bkz. `İZLEME.md`).
Sonraki temas noktaları: **14 Temmuz** (ilk hafta sonu sınavı sonucu), **~60. gün**
(z-skor aktivasyonu). Bu fazdan sonra yeni iş emri beklenmiyor.
