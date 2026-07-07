# TESLIMAT — Faz 3: Backtest Düzeltmeleri + GitHub + AI Paket + Trends

Tarih: 2026-07-07 · Python 3.12.4 · **69/69 test geçti** (61 → +8; öncekiler kırılmadı)

## Özet

| Bölüm | Durum |
|---|---|
| 0. Backtest metodoloji düzeltmeleri | ✅ taban çizgisi + örtüşmeyen pencere + DCA adaleti |
| 1. GitHub canlı + Actions arşivleyici | ✅ push edildi, workflow **başarıyla çalıştı**, CSV repoya düştü |
| 2. AI sentez paketi | ✅ `aipaket` + `/aipaket` (gerçek Telegram) |
| 3. Google Trends göstergesi | ✅ canlı + testli; **kontrarian yön doğrulanmadı** (dürüst) |
| 4. Dokümantasyon | ✅ rehber geri çekmeler, README, bu dosya |

---

## Bölüm 0 — Backtest metodoloji düzeltmeleri (yöneticinin 3 bulgusu)

### (1) Taban çizgisi + (2) örtüşmeyen pencere → rejim "üstünlükleri" ÇÖKTÜ

Faz 2 örtüşen pencere + taban çizgisiz idi → TL enflasyonu rejim başarısı gibi görünüyordu.
Düzeltme: **örtüşmeyen pencere** (bağımsız örneklem) + **"tüm günler" tabanına fark**.

| Rejim | FAZ 2 (yanıltıcı) | FAZ 3 (düzeltilmiş, gram TL tabandan fark) |
|---|---|---|
| A | "med +11.3%, kaz %88, DOĞRULANDI" | **fark −0.2p — üstünlük YOK** (etkin ~14 dönem) |
| C | "med +8.1%" | fark −1.6p |
| D | "med +11.5%, kaz %91, DOĞRULANDI" | **fark +1.4p — marjinal, zayıf N** (~12) |
| B | "kaz %42" | fark −15.0p ⚠️N=2 |
| Golden cross 6ay | "med +23.1%, kaz %97" | **fark +0.0p — üstünlük YOK** ⚠️N=11 |

**Dolar bazlı (ons, enflasyondan arınık): hiçbir rejimde anlamlı üstünlük yok** (A +0.1p, C +0.7p,
D −1.3p). Kazanma oranları Faz 2'de örtüşme nedeniyle abartılıydı. Raporda "Gün(etkin)" =
takvim günü/pencere ile kaba bağımsız dönem yazılıyor.

### (3) DCA adalet düzeltmesi

Prim-koşullu stratejide atlanan ay nakdi artık **EVDS mevduatında net faizle işler** (ölü nakit değil).

| Strateji | FAZ 2 (ölü nakit) | FAZ 3 (adil) tüm dönem | OOS (2023+) |
|---|---|---|---|
| DCA koşulsuz gram | +1736% (reel +43%) | +1736% (reel **+43%**) | reel −15% |
| DCA prim-koşullu | +2722% (şişik!) | +1697% (reel **+40%**) — koşulsuzdan **KÖTÜ** | reel −20% |
| TL mevduat | etiket belirsizdi | **EVDS TP.TRY.MT06, net=brüt×0.85**; reel −63% | reel −26% |

**❌ "Prim-koşullu üstünlük" çürütüldü** — Faz 2'deki fark ölü-nakit artefaktıydı (OOS'ta 38/43 ay
atlandı, ort. 12 ay bekleme). Mevduat etiketi netleşti: tarihsel EVDS serisi, net=brüt×0.85.

### (4) Rehber ✅/❌ yeniden değerlendirildi
PROJE-REHBERI'deki Faz 2 "DOĞRULANDI" blokları **geri çekildi**: rejim matrisi bu örneklemde
öngörü değeri taşımıyor; prim-koşullu DCA üstünlüğü çürütüldü. _"Sayıların küçülmesi dürüstlüğün
büyümesidir."_ 4 yeni test (örtüşmeyen<örtüşen, etkin dönem, nakit-park, dry-powder konuşlanma).

## Bölüm 1 — GitHub + Actions arşivleyici

- **Remote:** `origin → https://github.com/Mertsaglm/gold_tracking_system.git` eklendi.
- **Güvenlik:** `.env` git-ignore ✓ (yalnız `.env.example` izleniyor); `data/`+`reports/` dahil
  (private repo, tasarım gereği yedek).
- **Workflow** (`.github/workflows/archive.yml`): 15 dk cron, `pip install requests pyyaml yfinance`,
  `python -m src.archive_fetch`, GITHUB_TOKEN ile commit/push. **Secret yok.**
- **`archive_fetch` + `import_actions` yerel test edildi:** CSV satırı üretildi
  (`data/archive/2026-07.csv`), import prim_history'yi besledi (**geçerli prim 23→24**,
  z-skor arşivi doluyor); hafta sonu kayıtları `weekend=1` etiketi + weekend_expectation.
- **✅ CANLI:** `git push -u origin main` başarılı (dal master→main). Workflow API ile tetiklendi
  → **conclusion=success**; Actions bot'u repoya yeni CSV satırı ekledi (commit `9b6b11f`,
  satır `2026-07-07T18:30:01` ons=4153.0 — Actions'ın kendi çektiği taze fiyat). 15 dk cron aktif.
  Repo: https://github.com/Mertsaglm/gold_tracking_system

## Bölüm 2 — AI sentez paketi

`python -m src.aipaket` ve `/aipaket` (Telegram — gerçek gönderildi): SPK-uyumlu hazır prompt
(kişiye özel tavsiye yok, "kesin/garanti" yasak, geçersizlik zorunlu, **backtest alçakgönüllülük
notu**) + JSON veri paketi. Alanlar: fiyat, prim_zskoru (veri_bekliyor), makro (reel net mevduat
+%13.3), kadran, rejim + backtest köprüsü, **veri_kalitesi** (bacak durumu, z-skor arşivi
24/60 birikiyor, history/evds satır). Model çağrısı YOK — sıfır maliyet.

## Bölüm 3 — Google Trends kalabalık göstergesi

- `src/trends.py`: "gram altın" 5yıl haftalık z-skoru, **kontrarian etiketleme (4 test)**, 24s
  önbellek, panele bağlı. 429 rate-limit'te "veri yok" (GLD gibi paydadan çıkar).
- **Tarihsel doğrulama (Bölüm 0 metodolojisiyle) — kontrarian DOĞRULANMADI:** 11 ilgi zirvesi
  sonrası gram TL 1ay **+6.4p**, 3ay **+8.3p TABANIN ÜSTÜNDE** → momentum yönü, kontrarian değil.
  **AMA N=4-6 (çok zayıf) + zirveler 2018/2021 kur krizleriyle çakışıyor (enflasyon confounding).**
  Sonuç: gösterge panelde kalır, **düşük güven / yön belirsiz**, "doğrulanmış" sayılmaz. (Rehbere işlendi.)

## Test kırılımı (69)
```
calc(10) state_machine(16) indicators(9) evds_dates(7) backtest(15) signals(5)
calculators(7) trends(4)   → 69 passed
```

## Bilinen eksikler / sonraki
- **GitHub ilk push** kullanıcı auth'u bekliyor; sonrası Actions otomatik.
- Trends kontrarian yönü zayıf-N ve confounding nedeniyle belirsiz; arşiv/örneklem büyüyünce yeniden.
- Canlı günlük prim z-skoru arşivi <60 → Actions arşivi dolunca aktif olur.
- Ons GC=F futures; rejim/sinyal üstünlüğü bu örneklemde yok (dürüst sonuç).

## Tekrar üretmek
```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m src.backtest      # düzeltilmiş rapor
.venv/Scripts/python.exe -m src.aipaket
.venv/Scripts/python.exe -m src.archive_fetch && .venv/Scripts/python.exe -m src.import_actions
```
