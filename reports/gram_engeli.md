# Gram Engeli — "satmak gram kazandırır mı?"

_Ölçüm: 2016-01-04 → 2026-07-24 · 2561 gün · örtüşmeyen pencere · mevduat carry dahil (TP.TRY.MT03, stopaj %15) · tüm fazlar üzerinden_

Ölçülen büyüklük: **1 gram sat → TL'yi mevduatta beklet → geri al → kaç gram oldun?**

## Gidiş-dönüş maliyetleri

| Enstrüman | Gidiş-dönüş | Kaynak |
|---|---:|---|
| `banka_hesap` | %1.20 | `calculators.instrument_net` |
| `altins1` | %0.40 | `calculators.instrument_net` |
| `fiziki_gram` | %3.00 | `calculators.instrument_net` |

_`altin_fonu` listede yok: maliyeti gidiş-dönüş makası değil, zamana yayılı yönetim ücretidir._

## Ufuk bazında ölçüm

| Ufuk | Gün | N (bağımsız) | SAT gram kazancı (ort) | Medyan | SAT kazanır | Maliyet sonrası | En kötü |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1hafta | 5 | 512 | **-0.47%** | -0.50% | %42 | %24 | -24.0% |
| 1ay | 21 | 121 | **-1.99%** | -1.59% | %36 | %28 | -36.2% |
| 3ay | 63 | 40 | **-6.14%** | -6.15% | %22 | %19 | -49.4% |

## Sinyalin yenmesi gereken engel

| Ufuk | Taban | TAKTİK eşiği (SAT) | ÇEKİRDEK eşiği (az al) |
|---|---:|---:|---:|
| 1hafta | -0.47% | **+1.66p** | +0.47p |
| 1ay | -1.99% | **+3.18p** | +1.99p |
| 3ay | -6.14% | **+7.34p** | +6.14p |

_Taktik eşiği = |taban| + gidiş-dönüş (%1.20); çekirdek eşiği makas ödemez._

## Alt dönem kırılımı — artefakt mı, yapısal mı?

| Dönem | N | SAT gram kazancı (ort) | SAT kazanır |
|---|---:|---:|---:|
| 2016-19 | 46 | -1.35% | %39 |
| 2020-22 | 34 | -2.84% | %36 |
| 2023-26 | 39 | -1.98% | %33 |

**Tüm alt dönemlerde aynı işaret → dönem artefaktı değil, yapısal.**

## Faz artefaktı denetimi

Tek fazlı ölçüm (mevcut `chart.measure_edge` yöntemi) ile tüm-faz ortalaması arasındaki fark:

| Ufuk | Tek faz (faz 0) | Tüm faz ort. | Yayılım |
|---|---:|---:|---:|
| 1hafta | -0.46% | -0.47% | 0.02p |
| 1ay | -1.98% | -1.99% | 0.11p |
| 3ay | -6.20% | -6.14% | 0.70p |

_Yayılım, `config.yaml chart.dogrulama.min_anlamli_fark_puan` değerinden büyükse o ufukta tek-fazlı 'zayıf kanıt' bulguları faz artefaktından ayırt edilemez._

---
_Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir._