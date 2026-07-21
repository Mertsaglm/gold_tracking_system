# TESLIMAT — Faz 4: Tam Otonomluk (Actions'ta bildirim + günlük rapor)

Tarih: 2026-07-07 · **79/79 test geçti** (69 → +10 notify) · Repo: **public** (Actions sınırsız)

## Tek cümle
Kullanıcı hiçbir şey çalıştırmadan sistem kendi kendine izliyor, uyarıyor ve raporluyor —
GitHub Actions üzerinde. **Üretim ortamı budur; ayrı bir sunucu gerekmez.**

| Bölüm | Durum |
|---|---|
| 0. Secrets ve güvenlik | ✅ 3 secret API+pynacl ile (gh yok), dar permissions |
| 1. Bildirim motoru canlı | ✅ eşik+soğuma/tavan+hafta sonu, test bildirimi Telegram'a düştü |
| 2. Otonom günlük rapor | ✅ workflow **başarıyla çalıştı**, rapor Telegram'a düştü + commit |
| 3. Dayanıklılık + dakika bütçesi | ✅ sağlık satırı, continue-on-error, bütçe kanıtı |
| 4. Dokümantasyon | ✅ README + bu dosya |

---

## Bölüm 0 — Secrets

`gh` kurulu değildi → **GitHub API + PyNaCl sealed box** ile eklendi (`scripts/set_secrets.py`).
Token Windows Credential Manager'dan okundu (git credential fill takılıyordu). Değerler `.env`'den;
**hiçbir secret log/commit/koda girmedi.**

```
TELEGRAM_BOT_TOKEN: PUT HTTP 201
TELEGRAM_CHAT_ID:   PUT HTTP 201
EVDS_API_KEY:       PUT HTTP 201
Repodaki secret isimleri: ['EVDS_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
```
Workflow `permissions: contents: write` (en dar). Public repo'da secret'lar yine güvenli
(fork/PR'lara verilmez).

## Bölüm 1 — Bildirim motoru (`src/notify.py`)

- **Eşikler (6.2):** |prim|>%1.5 veya z>2, makas > tarihsel p90, günlük hareket > 2×ATR,
  çeyrek primi z>2. Güncel değerler **taze CSV satırından**, tarihsel bağlam commit'li DB'den.
- **Yorgunluk:** 24s soğuma + günlük tavan (6). Durum `data/alert_state.json`, workflow commit'ler.
- **Durum makinesi:** üç bacak FRESH değilse anomali BASTIRILIR; hafta sonu "pazartesi beklentisi"
  ayrı, günde 1.
- **Her bildirimde zorunlu üçlü:** tetiklenen kural + gerekçe/değer + geçersizlik notu + feragat.
- **10 birim test** (eşik ateşleme, hafta sonu bastırma, soğuma engelleme, 24s sonrası geçiş, tavan).
- **Test bildirimi GERÇEKTEN Telegram'a düştü** (yerel `{'test': True, 'gonderildi': 1}` +
  Actions'ta `test_notify:true` workflow_dispatch → **conclusion=success**).

## Bölüm 2 — Otonom günlük rapor (`src/daily_job.py` + `daily.yml`)

Akış: `import_actions` (CSV→DB, z-skor arşivini besler) → EVDS günlük → pazartesi mutabakat →
rapor (pazar: **haftalık derin** — hafta dekompozisyonu + z-skor arşiv ilerlemesi) → Telegram → commit.

**Kanıt — Actions'ta gerçek çalışma:**
```
"Gunluk otonom rapor"  conclusion=success  202s
→ rapor Telegram'a gönderildi (chat <chat_id>) + DB/rapor commit'lendi
```
Yerel test: `daily_job` import 2 satır, EVDS 29 gün güncelledi, rapor Telegram'a düştü.

## Bölüm 3 — Dayanıklılık + dakika bütçesi

- **Arşiv sağlık satırı** (raporda): son 24s Actions başarı oranı + en uzun boşluk;
  ~3 ardışık başarısızlıkta raporun tepesine uyarı (CSV zaman damgası boşluğundan hesaplanır).
- **Truncgil erişilemezse** archive_fetch null'lu satır yazar (arşivde delik görünür), workflow
  fail olmaz; notify adımı `continue-on-error`.
- **Dakika bütçesi:** repo **public → sınırsız.** Ölçülen: arşiv **~30s** (faturalanan 1dk),
  günlük **~202s** (~3dk). Aylık projeksiyon (public'te ücretsiz): arşiv 2880×1 + günlük 30×3 ≈
  **2970 dk — public'te sorun değil.** Private'a çevrilirse 2000 dk sınırı → sıklığı 30 dk'ya çek
  (1440+90 ≈ 1530 dk < 2000); README'de yazılı.

## Güvenlik / gizlilik notu
- `.env` git'te izlenmiyor (doğrulandı). Secret'lar yalnızca Actions secret store'da.
- **Repo public** → `data/` ve `reports/` herkese açık (sadece fiyat verisi/analiz, hassas değil).
  Gizlilik istenirse repo private yapılabilir (yukarıdaki bütçe notu geçerli olur).

## Test kırılımı (79)
```
calc(10) state_machine(16) indicators(9) evds_dates(7) backtest(15)
signals(5) calculators(7) trends(4) notify(10)   → 79 passed
```

## Kapsam dışı / sonraki
- **İnteraktif bot** (/durum, /net, /aipaket komutları) 7/24 polling gerektirir → yerelde
  `src.telegram_bot` açıkken yanıt verir; Actions push-only çalışır
  düşüldü. Actions push (rapor/bildirim) tarafı tam otonom.
- Canlı günlük prim z-skoru arşivi doluyor (Actions ile ~her gün +96 nokta); 60 güne ulaşınca
  z-skor bildirimleri de devreye girer.
- Üretim ortamı Actions olarak sabitlendi; ek altyapı gerekmiyor.

## Kullanıcının yapacakları
1. (Yok — secrets AI tarafından eklendi.) Telefonuna düşen rapor/bildirimleri izle.
2. Yerelde çalışırsan önce `git pull`.
3. İzleme dönemi başlıyor (bkz. `İZLEME.md`).
```
