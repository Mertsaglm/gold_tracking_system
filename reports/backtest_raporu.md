# 📈 Altın Backtest Raporu

Veri: 2016-01-04 → 2026-07-07 (2549 gün) · ons kaynak GC=F (futures) · gram = teorik has.

> Yöntem: look-ahead korumalı (giriş sinyal+1 gün). USD bazlı getiri = ons getirisi (kur etkisi arındırılmış). Gram TL = teorik has gram (canlı prim arşivi dolunca prim etkisi eklenecek — şu an aylık külçe proxy ayrı bölümde).

## Rejim Dağılımı (2016→bugün)

| Rejim | Gün | Tanım |
|---|---|---|
| A | 897 | ons>200GMA, reel faiz↓, kur baskılı |
| B | 26 | ons>200GMA, reel faiz↓, kur serbest |
| C | 498 | ons<200GMA, reel faiz↑ |
| D | 796 | ons>200GMA, reel faiz↑ (anomali/MB alım rejimi) |
| X | 332 | sınıflanamayan |

## Rejim Başına 3 Ay İleri Getiri

| Rejim | Gram TL | Dolar bazlı (ons) |
|---|---|---|
| A | med +11.3% · ort +12.7% · kaz %88 · N=893 | med +5.0% · ort +5.6% · kaz %70 · N=893 |
| B | med -2.0% · ort +5.9% · kaz %42 · N=26 | med -4.3% · ort -0.8% · kaz %38 · N=26 |
| C | med +8.1% · ort +9.7% · kaz %82 · N=477 | med +4.4% · ort +3.7% · kaz %76 · N=477 |
| D | med +11.5% · ort +11.5% · kaz %91 · N=757 | med +2.8% · ort +3.0% · kaz %64 · N=757 |
| X | med +6.1% · ort +11.2% · kaz %81 · N=332 | med +1.1% · ort +0.7% · kaz %55 · N=332 |

_Rehber 2.3 rejim matrisi iddiaları bu tabloyla veriyle test edildi._

## Sinyal Demo: Ons 200GMA Üstüne Kırılım

- 1ay sonra gram TL: med +3.7% · ort +5.0% · kaz %78 · N=37
- 3ay sonra gram TL: med +10.1% · ort +13.0% · kaz %89 · N=37
- 6ay sonra gram TL: med +23.1% · ort +30.7% · kaz %97 · N=37

_(Sinyal 37 kez oluştu.)_

## DCA Karşılaştırması (aylık birikim)

_Prim-koşullu alım aylık külçe proxy (saflık bazı: has (1000/1000) — külçe teorik ile ~birebir); aylık çözünürlük — günlük prim değil._

### Tüm dönem (2016-01-01→2026-07-01, 127 ay)

| Strateji | Nominal getiri | TÜFE-reel | Maks. geri çekilme |
|---|---|---|---|
| DCA koşulsuz (aylık gram) | +1736% | +43% | -18% |
| DCA prim-koşullu | +2722% | +120% | -18% |
| TL mevduat (net %85) | +368% | -63% | — |

## Out-of-Sample Disiplini

Parametre/eşik dönemi (in-sample) < 2023-01-01, test dönemi ≥ 2023-01-01. Ayrı raporlanır.

### In-sample (< 2023-01-01) (2016-01-01→2022-12-01, 84 ay)

| Strateji | Nominal getiri | TÜFE-reel | Maks. geri çekilme |
|---|---|---|---|
| DCA koşulsuz (aylık gram) | +369% | +14% | -17% |
| DCA prim-koşullu | +441% | +32% | -17% |
| TL mevduat (net %85) | +61% | -61% | — |

### Out-of-sample (≥ 2023-01-01) (2023-01-01→2026-07-01, 43 ay)

| Strateji | Nominal getiri | TÜFE-reel | Maks. geri çekilme |
|---|---|---|---|
| DCA koşulsuz (aylık gram) | +148% | -15% | -15% |
| DCA prim-koşullu | +33% | -54% | -7% |
| TL mevduat (net %85) | +117% | -26% | — |

### Rejim dağılımı OOS kırılımı

- In-sample gün: 1701 · Out-of-sample gün: 848

---
_Genel bilgilendirme; yatırım tavsiyesi değildir. Geçmiş performans gelecek getiriyi garanti etmez._