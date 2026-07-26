# Gram Aday Taraması — 1ay ufku

> ⚠️ **BU BİR KARNE DEĞİLDİR.** Buradaki eşiklerin bir kısmı bu veriye bakılarak seçildi; ölçüm örneklem-**İÇİ**dir ve gerçek performansı OLDUĞUNDAN İYİ gösterir. Tek gerçek örneklem-dışı kayıt `predictions` tablosunda `kaynak='canli'` satırlarındadır.
>
> Bu tablonun tek meşru kullanımı **aday elemektir**: örneklem-içi ölçümde bile eşiği aşamayan bir aday, canlıda hiç aşamaz.

_Tarama: 2017-01-19 → 2026-07-24 · 458 haftalık asof · örtüşmeyen pencere · tüm fazlar · gidiş-dönüş %1.20_

## Aşılması gereken eşik

- Taban (SAT'ın koşulsuz gram kazancı): **%-1.99** (N=121 bağımsız pencere)
- Bir adayın kârlı olması için tabanı yenmesi gereken fark: **+3.18 puan**

## Adaylar (fark büyükten küçüğe)

| Aday | N | Ort. gram kazancı | Tabana fark | t | Kazanma | Eşiği geçti? |
|---|---:|---:|---:|---:|---:|:--:|
| kur oynaklık > %25 (şok) | 6 ⚠️ | %+0.87 | **+2.85p** | +1.01 | %50 | ❌ |
| reel_mevduat > %10 | 22 ⚠️ | %-0.64 | **+1.34p** | +1.03 | %45 | ❌ |
| gram RSI < 30 | 4 ⚠️ | %-1.16 | **+0.83p** | +0.31 | %25 | ❌ |
| gram 12ay momentum > %60 | 47 | %-1.53 | **+0.45p** | +0.55 | %38 | ❌ |
| ons 200GMA üstü %15+ | 20 ⚠️ | %-1.89 | **+0.10p** | +0.08 | %35 | ❌ |
| kur bacağı payı > 0.7 | 49 | %-2.29 | **-0.30p** | -0.33 | %33 | ❌ |
| gram Donchian55 tepede (>0.95) | 51 | %-2.34 | **-0.35p** | -0.35 | %35 | ❌ |
| kur oynaklık < %5 (sürünme) | 30 | %-2.46 | **-0.47p** | -0.49 | %33 | ❌ |
| ons RSI > 75 | 13 ⚠️ | %-2.60 | **-0.62p** | -0.40 | %46 | ❌ |
| gram RSI > 75 | 22 ⚠️ | %-2.66 | **-0.68p** | -0.50 | %32 | ❌ |
| ons Donchian55 tepede (>0.95) | 34 | %-2.76 | **-0.77p** | -0.64 | %29 | ❌ |
| gram 200GMA üstü %15+ | 55 | %-2.77 | **-0.78p** | -0.89 | %27 | ❌ |
| reel_mevduat < 0 | 34 | %-3.04 | **-1.06p** | -0.80 | %38 | ❌ |
| gram 3ay momentum > %25 | 20 ⚠️ | %-3.21 | **-1.22p** | -0.55 | %50 | ❌ |

_⚠️ = N < 30, ölçüm yetersiz._

## Hüküm

**Hiçbir aday eşiği geçmedi.** Örneklem-içi ölçümde bile aşılamayan bir eşik, canlıda hiç aşılmaz. Taktik kol kapalı kalmalı; yeni aday aranmadan SAT açılmamalı.

> 14 karşılaştırma yapıldı; en iyi görünen sonucun şansa bağlı olma olasılığı yüksektir. Tek tek 'en iyi' satıra bakmayın.

---
_Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir._