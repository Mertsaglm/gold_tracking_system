# Grafik Doğrulama Raporu

Seri: **GC=F** · 2653 bar (2016-01-04 → 2026-07-24)

> **Seviyeler geometridir; 'fark' sütunu ölçümdür.** Fark ≈0 ise seviyenin yön
> bilgisi yoktur — kademe/stop planlaması için yine kullanılabilir (mekanik kural),
> **yön iddiası için kullanılamaz.**

> 54 karşılaştırma yapıldı; en iyi görünen sonucun şansa bağlı olma olasılığı yüksektir. Tek tek 'en iyi' satıra bakmayın.

> Hacim ağırlıklandırması KULLANILMADI (GC=F hacmi ön-vade kontrat hacmi;
> TRY=X hacmi 0). MACD dışarıda (50/200 GMA ile eşdoğrusal).

> **Taban tüm fazlardan ölçülür (ADR #007-E).** `faz yayılımı`, hiçbir
> sinyal olmadan yalnız pencere hizasından doğan farktır; ölçüm eşiği
> ondan küçük olamaz. Bir ufukta yayılım büyükse o ufuk, elimizdeki
> veriyle **ölçülemez** demektir — bulgu yok demek değil, ölçüm yok demek.

## Desteğe yakın

- **1ay** (tüm dönem): med +0.4% · kaz %56 · N=50 · taban +0.7% · **fark -0.3p** → _kenar yok_ · etkin dönem ~17
  - faz yayılımı **1.0p** → kullanılan eşik **1.0p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _kenar yok_
- **3ay** (tüm dönem): med +2.7% · kaz %67 · N=24 · taban +3.5% · **fark -0.8p** → _kenar yok_ · etkin dönem ~5
  - faz yayılımı **4.1p** → kullanılan eşik **4.1p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _ölçüm yetersiz (N=9)_
- **6ay** (tüm dönem): med +10.1% · kaz %79 · N=14 ⚠️zayıf · taban +6.4% · **fark +3.8p** → _ölçüm yetersiz (N=14)_ · etkin dönem ~2
  - faz yayılımı **7.4p** → kullanılan eşik **7.4p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=9)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=5)_

## Dirence yakın

- **1ay** (tüm dönem): med +1.2% · kaz %57 · N=51 · taban +0.7% · **fark +0.4p** → _kenar yok_ · etkin dönem ~17
  - faz yayılımı **1.0p** → kullanılan eşik **1.0p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _ölçüm yetersiz (N=14)_
- **3ay** (tüm dönem): med +3.4% · kaz %71 · N=21 · taban +3.5% · **fark -0.1p** → _kenar yok_ · etkin dönem ~5
  - faz yayılımı **4.1p** → kullanılan eşik **4.1p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _ölçüm yetersiz (N=6)_
- **6ay** (tüm dönem): med +8.6% · kaz %77 · N=13 ⚠️zayıf · taban +6.4% · **fark +2.2p** → _ölçüm yetersiz (N=13)_ · etkin dönem ~2
  - faz yayılımı **7.4p** → kullanılan eşik **7.4p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=9)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=5)_

## RSI aşırı satım

- **1ay** (tüm dönem): med +2.7% · kaz %69 · N=16 · taban +0.7% · **fark +2.0p** → _zayıf kanıt: +2.0p_ · etkin dönem ~4
  - faz yayılımı **1.0p** → kullanılan eşik **1.0p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=12)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=4)_
- **3ay** (tüm dönem): med -0.9% · kaz %38 · N=8 ⚠️zayıf · taban +3.5% · **fark -4.4p** → _ölçüm yetersiz (N=8)_ · etkin dönem ~1
  - faz yayılımı **4.1p** → kullanılan eşik **4.1p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=6)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=2)_
- **6ay** (tüm dönem): med +4.5% · kaz %67 · N=6 ⚠️zayıf · taban +6.4% · **fark -1.9p** → _ölçüm yetersiz (N=6)_ · etkin dönem ~1
  - faz yayılımı **7.4p** → kullanılan eşik **7.4p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=5)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=1)_

## RSI aşırı alım

- **1ay** (tüm dönem): med +1.2% · kaz %66 · N=32 · taban +0.7% · **fark +0.5p** → _kenar yok_ · etkin dönem ~11
  - faz yayılımı **1.0p** → kullanılan eşik **1.0p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _kenar yok_
- **3ay** (tüm dönem): med +1.3% · kaz %70 · N=20 · taban +3.5% · **fark -2.2p** → _kenar yok_ · etkin dönem ~3
  - faz yayılımı **4.1p** → kullanılan eşik **4.1p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=13)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=7)_
- **6ay** (tüm dönem): med +11.3% · kaz %79 · N=14 ⚠️zayıf · taban +6.4% · **fark +4.9p** → _ölçüm yetersiz (N=14)_ · etkin dönem ~1
  - faz yayılımı **7.4p** → kullanılan eşik **7.4p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=10)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=5)_

## Bollinger alt

- **1ay** (tüm dönem): med +1.1% · kaz %75 · N=40 · taban +0.7% · **fark +0.4p** → _kenar yok_ · etkin dönem ~5
  - faz yayılımı **1.0p** → kullanılan eşik **1.0p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _ölçüm yetersiz (N=10)_
- **3ay** (tüm dönem): med +2.7% · kaz %70 · N=23 · taban +3.5% · **fark -0.8p** → _kenar yok_ · etkin dönem ~1
  - faz yayılımı **4.1p** → kullanılan eşik **4.1p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _ölçüm yetersiz (N=6)_
- **6ay** (tüm dönem): med +6.7% · kaz %71 · N=14 ⚠️zayıf · taban +6.4% · **fark +0.4p** → _ölçüm yetersiz (N=14)_ · etkin dönem ~1
  - faz yayılımı **7.4p** → kullanılan eşik **7.4p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=10)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=4)_

## Bollinger üst

- **1ay** (tüm dönem): med +1.2% · kaz %55 · N=58 · taban +0.7% · **fark +0.5p** → _kenar yok_ · etkin dönem ~10
  - faz yayılımı **1.0p** → kullanılan eşik **1.0p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _kenar yok_
- **3ay** (tüm dönem): med +3.3% · kaz %63 · N=30 · taban +3.5% · **fark -0.2p** → _kenar yok_ · etkin dönem ~3
  - faz yayılımı **4.1p** → kullanılan eşik **4.1p** (config alt sınırı 1.0p)
  - in-sample: _kenar yok_ · OOS (2023-01-01+): _ölçüm yetersiz (N=10)_
- **6ay** (tüm dönem): med +8.8% · kaz %82 · N=17 · taban +6.4% · **fark +2.5p** → _kenar yok_ · etkin dönem ~1
  - faz yayılımı **7.4p** → kullanılan eşik **7.4p** (config alt sınırı 1.0p)
  - in-sample: _ölçüm yetersiz (N=11)_ · OOS (2023-01-01+): _ölçüm yetersiz (N=6)_

---
_Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir._