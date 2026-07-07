# TESLIMAT — Faz 2: Kritik Düzeltme + Backtest + Sinyal + Hesaplayıcılar

Tarih: 2026-07-07 · Ortam: Windows (geliştirme), Python 3.12.4, .venv · Hedef: Oracle

## Özet

| Bölüm | Durum |
|---|---|
| 0. evds_daily tarih ISO düzeltmesi (KRİTİK) | ✅ düzeltildi + regresyon testi |
| 1. Tarihsel veri katmanı (2016+) | ✅ history_daily 2549 gün, külçe saflık tespiti |
| 2. Backtest motoru | ✅ rejim + sinyal + DCA + out-of-sample raporu |
| 3. Sinyal motoru (on-demand) | ✅ JSON şema + backtest köprüsü + rapora/Telegram |
| 4. Net getiri hesaplayıcıları | ✅ CLI + /net /bilezik (gerçek Telegram gönderimi) |
| 5. GLD tonaj | ✅ AUM'dan seviye (973 ton) + snapshot arşivi |
| 6. GitHub Actions | ⛔ kullanıcı atladı |
| 7. Dokümantasyon | ✅ rehber doğrulanmış notları, README, bu dosya |
| **Testler** | ✅ **61/61 geçti** (31 → +30 yeni; öncekiler kırılmadı) |

---

## Bölüm 0 — KRİTİK: evds_daily tarih ISO düzeltmesi

**Kusur:** tarihler ham `GG-AA-YYYY` metni → `ORDER BY date` kronolojik değil
("01-01-2018" < "01-02-2016").

**Çözüm:** `evds.to_iso_date()` — günlük `GG-AA-YYYY`→`YYYY-MM-DD`, aylık `2016-1`→`2016-01-01`,
çeyreklik `Q1`→ay, zaten-ISO dokunulmaz. Parser her satırda uygular. 7531 satır silinip
ISO ile yeniden backfill edildi.

**Diğer tablolar denetlendi:** ticks/prim_history/weekend_expectation = ISO 8601
(`util.iso`), ohlc_1m = `YYYY-MM-DDTHH:MM`, reports.date = `YYYY-MM-DD`. **Yalnız evds_daily
bozuktu, düzeltildi.** `evds_job._latest/_tufe_yoy` artık `ORDER BY date`.

**Kanıt (düzeltme sonrası):**
```
ORDER BY date ASC  LIMIT 1 (USD)  -> 2015-01-02  (value 2.3311  ✓ 2015 için doğru)
ORDER BY date DESC LIMIT 1 (USD)  -> 2026-07-08
aylık külçe DESC                   -> 2026-05-01  (ISO ay başı)
BETWEEN 2020-01-01..2020-12-31    -> 252 satır  (doğru günlük)
```
**Regresyon testi:** `tests/test_evds_dates.py` (7 test) — dönüşüm + `ORDER BY date` ilk=en eski,
son=en yeni + `BETWEEN` doğru sayı.

## Bölüm 1 — Tarihsel veri katmanı

- **history_daily: 2549 gün** (2016-01-04 → 2026-07-07). yfinance ons (XAUUSD=X 404 verdi →
  **GC=F futures** fallback) × EVDS günlük USD → teorik has gram TL. ons_source etiketli.
- **Külçe saflık tespiti:** külçe/teorik oran medyanı **1.0105** → **has (1000/1000) bazı**
  (995 DEĞİL; %1 fark GC=F contango'sundan). Faz 1'deki %0.5 saflık dersi burada da uygulandı.
- **Veri kalitesi:** günlük vol %1.50; **3 aykırı (>6σ) hepsi gerçek kur şoku** — 2018-08-14
  (+16%, lira krizi), 2021-12-22 (−25%, KKM günü), 2026-01-30 (−11%); veri hatası değil.
  7 günlük boşluklar tatil dönemleri (Temmuz 2016, Kurban).

## Bölüm 2 — Backtest motoru (`reports/backtest_raporu.md`)

Look-ahead korumalı (giriş sinyal+1 gün). Çekirdek fonksiyonlar **11 birim testli**
(sentetik seri → bilinen çıktı).

**Rejim başına 3 ay ileri getiri (gram TL):**
| Rejim | Gün | Gram TL medyan | Kazanma | Dolar bazlı (ons) |
|---|---|---|---|---|
| A | 897 | +11.3% | %88 | +5.0% |
| B | 26 | −2.0% | %42 | ⚠️ N zayıf |
| C | 498 | +8.1% | %82 | +4.4% |
| D | 796 | +11.5% | %91 | +2.8% |

**Sinyal demo — ons 200GMA kırılımı (37 kez):** 1ay +3.7%, 3ay +10.1%, **6ay +23.1% (kazanma %97)**.

**DCA (2016→2026, aylık):**
| Strateji | Tüm dönem nominal | Tüm dönem reel | In-sample reel | OOS (2023+) reel |
|---|---|---|---|---|
| Koşulsuz gram DCA | +1736% | **+43%** | +14% | **−15%** |
| Prim-koşullu gram | +2722% | — | +32% | (OOS'ta zayıf) |
| TL mevduat (net) | +368% | çok geride | **−61%** | +117% nominal |

**Ana bulgu:** altın in-sample'da satın alma gücünü korudu (mevduat eritti), OOS'ta (2023+ aşırı
enflasyon) TL reel kaybetti — "altın her zaman korur" çürütüldü, rejime bağlı. Out-of-sample
ayrı raporlandı (in-sample < 2023-01-01, test ≥ 2023-01-01).

## Bölüm 3 — Sinyal motoru (`src/signals.py`)

PROJE-REHBERI 6.3 şeması: her sinyalde **gerekçe + güven + geçersizlik + backtest köprüsü**.
5 sinyal üretiliyor. Örnek (rejim sinyali, backtest köprüsü gerçek istatistik iliştiriyor):
```
rejim → "zayıf rejim" (C) · güven: orta
  📊 Backtest: Bu rejim 2016'dan beri 477 gün; 3 ay sonra gram TL medyan +8.1%, kazanma %82.
  ❌ Geçersizlik: Ons 200GMA'yı veya reel faiz trendini kırarsa rejim değişir.
```
- **prim_zskoru → "veri_bekliyor"** (canlı arşiv 23/60 < eşik — doğru şekilde pas geçiyor).
- Backtest karşılığı olmayanlar açıkça **"tarihsel doğrulaması yok"** yazıyor.
- Sinyaller günlük rapora **"Sinyaller" bölümü** olarak girdi ve **Telegram'a gönderildi** (kanıt: log).
- Bildirim eşik değerlendirmesi (`evaluate_alerts`, rehber 6.2) kod olarak hazır; şu an tetik yok
  (`[]`); zamanlayıcı Oracle'a bırakıldı.

## Bölüm 4 — Hesaplayıcılar (`src/calculators.py`)

**7 birim testli.** CLI + Telegram (`/net`, `/bilezik`) — **gerçek Telegram gönderimi yapıldı.**
```
/net 100000 12 30:
  altins1 129,481₺ (+29.5%) · banka_hesap 128,446 (+28.4%) · fiziki 126,100 · fon 124,395 (+24.4%)
  Kazanan: altins1 · Banka↔fon kırılım: 4 ay
/bilezik 20 20:
  hurda 113,759₺ · %20 işçilik → ödenen 136,511₺ · başabaş için gram +%20 (işçilik geri satışta yanar)
```
Fon %15 stopajla en geride; ALTINS1 en düşük maliyetle önde. Tüm oranlar `config.yaml`.

## Bölüm 5 — GLD tonaj (30 dk kutulu)

Eski `spdrgoldshares.com` arşiv CSV'si artık **PDF** dönüyor (denendi, doğrulandı). Çözüm:
**yfinance GLD.info `totalAssets` / altın_ons / (ons/ton) = 973 ton** (GLD için doğru mertebede).
Günlük snapshot `gld_tonnage` tablosuna yazılıyor; trend için arşiv birikince (Oracle'da) %değişim
hesaplanacak — şu an "1. gözlem, veri birikiyor" (dürüst; paydadan çıkıyor).

## Bölüm 7 — Dokümantasyon

- **PROJE-REHBERI.md:** rejim matrisine, prim ortalamaya dönüşe, DCA'ya **✅ doğrulanmış /
  ❌ çürütülmüş / ⏳ test edilemedi** notları işlendi — rehber artık test edilmiş bilgi belgesi.
- **README.md:** yeni komutlar (history, backtest, signals, calculators, /net, /bilezik).
- **Bu dosya.**

## Test kırılımı (61 toplam)
```
test_calc (10) · test_state_machine (16) · test_indicators (9) · test_evds_dates (7)
test_backtest (11) · test_signals (5) · test_calculators (7)   → 61 passed
```

## Veri durumu (kanıt)
```
evds_daily 7531 (2015-01-02 .. 2026-07-08, ISO sıralı)
history_daily 2549 (2016+)  ·  gld_tonnage 1  ·  prim_history 23  ·  ticks 175
```

## Bilinen eksikler / sonraki
- Canlı günlük Kapalıçarşı prim arşivi <60 kayıt → prim z-skoru ve günlük prim mean-reversion
  backtest'i Oracle'da arşiv dolunca yapılacak.
- Ons kaynağı GC=F (futures); spot XAU ücretsiz kaynağı bulunursa prim tabanı iyileşir.
- GLD tonaj trendi arşiv birikimine bağlı.
- v3: AI sentez katmanı, Google Trends kalabalık göstergesi (bkz. rehber backlog).

## Tekrar üretmek
```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m src.evds_job backfill
.venv/Scripts/python.exe -m src.history build
.venv/Scripts/python.exe -m src.backtest
.venv/Scripts/python.exe -m src.signals
.venv/Scripts/python.exe -m src.calculators 100000 12 30
```
