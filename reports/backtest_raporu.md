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

## Rejim Başına 3 Ay İleri Getiri (örtüşmeyen pencere)

> Örtüşen günlük pencereler bağımsız değil; **örtüşmeyen** pencere kullanıldı, her satırda **tabandan (tüm günler) fark** verildi. Bilgi değeri = farktır; mutlak medyan TL enflasyonu artefaktıdır.

| Rejim | Gün(etkin) | Gram TL vs taban | Dolar bazlı (ons) vs taban |
|---|---|---|---|
| **Taban (tüm günler)** | 2549(40) | med +10.9% · kaz %85 | med +3.4% · kaz %74 |
| A | 897(14) | med +10.6% · kaz %86 · N=22 · taban +10.9% · **fark -0.2p** | med +3.5% · kaz %73 · N=22 · taban +3.4% · **fark +0.1p** |
| B | 26(1) | med -4.1% · kaz %0 · N=2 ⚠️zayıf · taban +10.9% · **fark -15.0p** | med +1.8% · kaz %50 · N=2 ⚠️zayıf · taban +3.4% · **fark -1.6p** |
| C | 498(7) | med +9.3% · kaz %88 · N=16 · taban +10.9% · **fark -1.6p** | med +4.1% · kaz %81 · N=16 · taban +3.4% · **fark +0.7p** |
| D | 796(12) | med +12.2% · kaz %84 · N=25 · taban +10.9% · **fark +1.4p** | med +2.0% · kaz %68 · N=25 · taban +3.4% · **fark -1.3p** |
| X | 332(5) | med +9.0% · kaz %100 · N=9 ⚠️zayıf · taban +10.9% · **fark -1.9p** | med -1.0% · kaz %44 · N=9 ⚠️zayıf · taban +3.4% · **fark -4.4p** |

_'Gün(etkin)' = takvim günü (kaba bağımsız dönem). Fark ≈0 veya negatifse rejimin bilgi değeri yok. Rehber iddiaları buna göre yeniden değerlendirildi._

## Sinyal Demo: Ons 200GMA Üstüne Kırılım (taban karşılaştırmalı)

- 1ay: med +3.1% · kaz %71 · N=21 · taban +3.3% · **fark -0.3p**
- 3ay: med +7.6% · kaz %79 · N=14 ⚠️zayıf · taban +10.9% · **fark -3.3p**
- 6ay: med +21.0% · kaz %100 · N=11 ⚠️zayıf · taban +20.9% · **fark +0.0p**

_(Sinyal 37 kez; örtüşmeyen pencerelerle N küçülür — kesinlik iddiası buna göre.)_

## DCA Karşılaştırması (aylık birikim)

_Prim-koşullu alım aylık külçe proxy (saflık bazı: has (1000/1000) — külçe teorik ile ~birebir); aylık çözünürlük — günlük prim değil. Alınmayan ay nakdi EVDS mevduatında net faizle işler (adil karşılaştırma). Mevduat faizi = EVDS TP.TRY.MT06 tarihsel serisi._

### Tüm dönem (2016-01-01→2026-07-01, 127 ay)

| Strateji | Nominal | TÜFE-reel | Maks. geri çekilme |
|---|---|---|---|
| DCA koşulsuz (aylık gram) | +1736% | +43% | -18% |
| DCA prim-koşullu (nakit mevduatta) | +1697% | +40% | -18% |
| TL mevduat (EVDS 1yıl, net=brüt×0.85) | +368% | -63% | — |

_Prim-koşullu: 65/127 ay atlandı (nakit mevduatta faiz işledi), ort. bekleme 3.7 ay._

## Out-of-Sample Disiplini

Parametre/eşik dönemi (in-sample) < 2023-01-01, test dönemi ≥ 2023-01-01. Ayrı raporlanır.

### In-sample (< 2023-01-01) (2016-01-01→2022-12-01, 84 ay)

| Strateji | Nominal | TÜFE-reel | Maks. geri çekilme |
|---|---|---|---|
| DCA koşulsuz (aylık gram) | +369% | +14% | -17% |
| DCA prim-koşullu (nakit mevduatta) | +362% | +12% | -17% |
| TL mevduat (EVDS 1yıl, net=brüt×0.85) | +61% | -61% | — |

_Prim-koşullu: 27/84 ay atlandı (nakit mevduatta faiz işledi), ort. bekleme 1.4 ay._

### Out-of-sample (≥ 2023-01-01) (2023-01-01→2026-07-01, 43 ay)

| Strateji | Nominal | TÜFE-reel | Maks. geri çekilme |
|---|---|---|---|
| DCA koşulsuz (aylık gram) | +148% | -15% | -15% |
| DCA prim-koşullu (nakit mevduatta) | +134% | -20% | -14% |
| TL mevduat (EVDS 1yıl, net=brüt×0.85) | +117% | -26% | — |

_Prim-koşullu: 38/43 ay atlandı (nakit mevduatta faiz işledi), ort. bekleme 12.0 ay._

### Rejim dağılımı OOS kırılımı

- In-sample gün: 1701 · Out-of-sample gün: 848

---
_Genel bilgilendirme; yatırım tavsiyesi değildir. Geçmiş performans gelecek getiriyi garanti etmez._