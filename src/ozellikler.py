"""Bölüm 8d — Özellik katmanı: look-ahead'e karşı YAPISAL savunma.

Bu modülün varlık sebebi tek bir cümledir:

    Canlı üretim ve tarihsel replay **aynı fonksiyonu** çağırır.

Look-ahead sızıntısı, "geçmişi test ederken bugünün bilgisini kullanmak"tır ve
backtest'lerin en yaygın ölüm sebebidir. Klasik hata, canlı kodun bir yolla,
backtest kodunun başka bir yolla veri okumasıdır — ikisi zamanla ayrışır ve
backtest sessizce geleceği görmeye başlar. Tek giriş noktası bunu disiplinle
değil **yapısal olarak** engeller: `feature_vector` `asof_date`'ten sonraki
hiçbir satırı okumaz, ve okuyan tek kod yolu budur.

## `asof_date` ne demek

**SON TAM KAPANMIŞ gün (T−1).** `daily.yml` 15:35 UTC'de koşuyor; o saatte
GC=F'in O GÜNKÜ kapanışı (CME ~21:00 UTC) HENÜZ YOK. Bugünün `history_daily`
satırını okumak, canlıda var olmayan bir bilgiyi kullanmak olurdu.

## Neden bazı kaynaklar DIŞARIDA (repo kuralı: red gerekçesiyle kayda geçer)

| Kaynak | Neden |
|---|---|
| `gld_tonnage` | 19 satır (2026-07-07'den) — tarihçe yok, replay'de hep boş |
| `prim_history` | ~250 kayıt / 19 gün — aynı sorun. Kapı açılınca eklenir |
| FRED DFII10/DXY | Üretimde 2026-07-07'den beri ölü. **Canlıda hesaplanamayan bir özelliğin karnesi sahtedir** |
| Google Trends | `today 5-y` değerleri pencere maksimumuna normalize edilir → bugün çekilen 2018 değeri GELECEĞİ İÇERİR |
| gram TL OHLC | Üretilmiyor (`db.py` şema notu: high_ons × high_usd aynı ana ait değil) → gram için yalnız kapanış serisi |

Kalan kaynaklar (`history_daily`, `ohlc_daily`, `evds_daily`) hem 2016'ya kadar
uzanıyor hem de canlıda çalışıyor — yani **kesişim**. Karne ancak bu kesişim
üzerinde dürüst olur.

## EVDS yayın gecikmesi

`evds_daily.date` **dönem başıdır, yayın tarihi değil.** TÜFE ayın ~3'ünde
önceki ay için yayınlanır; `date <= asof` filtresi tek başına 1-35 gün geleceği
sızdırır. Bu yüzden her seri `config.yaml karar.evds_yayin_gecikme_gun`
değeriyle geriye kaydırılır.
"""
from __future__ import annotations

import bisect
import logging
import math
import statistics
from datetime import date, timedelta
from typing import Optional, Sequence

from . import util

log = logging.getLogger("ozellikler")

# Ufuk pencereleri (işlem günü) — momentum ve oynaklık için
MOM_PENCERELERI = {"1ay": 21, "3ay": 63, "6ay": 126, "12ay": 252}
VOL_PENCERE = 60
GMA_PENCERE = 200
DONCHIAN = (20, 55)


# ================= SAF ÇEKİRDEK (testli) =================

def gunler_once(iso: str, gun: int) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return (date(y, m, d) - timedelta(days=gun)).isoformat()


def getiri_pct(seri: Sequence[float], pencere: int) -> Optional[float]:
    """Son değerin `pencere` gün öncesine göre yüzde değişimi."""
    if len(seri) <= pencere:
        return None
    o, s = seri[-1 - pencere], seri[-1]
    return ((s / o) - 1.0) * 100.0 if o else None


def hareketli_ortalama(seri: Sequence[float], pencere: int) -> Optional[float]:
    return statistics.mean(seri[-pencere:]) if len(seri) >= pencere else None


def yillik_oynaklik_pct(seri: Sequence[float], pencere: int) -> Optional[float]:
    """Log-getirilerin yıllıklaştırılmış standart sapması (%)."""
    if len(seri) < pencere + 1:
        return None
    lr = [math.log(seri[i] / seri[i - 1])
          for i in range(len(seri) - pencere, len(seri))
          if seri[i] and seri[i - 1]]
    if len(lr) < 2:
        return None
    return statistics.pstdev(lr) * math.sqrt(252) * 100.0


def donchian_konum(seri: Sequence[float], pencere: int) -> Optional[float]:
    """Son fiyatın `pencere` günlük kanal içindeki yeri: 0=dip, 1=tepe.

    Neden Donchian: en çok backtest edilmiş trend kuralıdır (turtle) ve tek
    sayıya iner — eşik gerektirmez, kanal kırılımı kendiliğinden ölçülür.
    """
    if len(seri) < pencere:
        return None
    p = seri[-pencere:]
    lo, hi = min(p), max(p)
    return (seri[-1] - lo) / (hi - lo) if hi > lo else 0.5


def z_konum(deger: Optional[float], seri: Sequence[float],
            pencere: int) -> Optional[float]:
    """Değerin kendi geçmiş dağılımındaki z konumu (persentil yerine z)."""
    if deger is None or len(seri) < pencere:
        return None
    p = seri[-pencere:]
    sd = statistics.pstdev(p)
    return (deger - statistics.mean(p)) / sd if sd else 0.0


# ================= IO: asof-güvenli okuma =================

def _asof_seri(con, sorgu: str, params: tuple) -> tuple[list[str], list[float]]:
    rows = con.execute(sorgu, params).fetchall()
    return [r[0] for r in rows], [r[1] for r in rows]


def evds_asof(con, series_code: str, asof_date: str,
              gecikme_gun: int) -> Optional[float]:
    """`asof_date`te YAYINLANMIŞ olan son değer.

    `date + gecikme_gun <= asof` — yani serinin dönem tarihi değil, o dönemin
    yayınlandığı varsayılan tarih dikkate alınır. Gecikmeyi ihmal etmek,
    henüz açıklanmamış bir TÜFE'yi biliyormuş gibi davranmaktır.
    """
    kesim = gunler_once(asof_date, gecikme_gun)
    r = con.execute(
        "SELECT value FROM evds_daily WHERE series_code=? AND value IS NOT NULL "
        "AND date <= ? ORDER BY date DESC LIMIT 1", (series_code, kesim)).fetchone()
    return r["value"] if r else None


def _ohlc_asof(con, symbol: str, asof_date: str, limit: int = 400):
    rows = con.execute(
        "SELECT date,o,h,l,c FROM ohlc_daily WHERE symbol=? AND date <= ? "
        "AND c IS NOT NULL ORDER BY date DESC LIMIT ?",
        (symbol, asof_date, limit)).fetchall()
    rows = list(reversed(rows))
    return ([r["h"] for r in rows], [r["l"] for r in rows], [r["c"] for r in rows])


def son_kapali_gun(con, bugun: Optional[str] = None) -> Optional[str]:
    """asof = SON TAM KAPANMIŞ gün — `bugun` DAİMA dışlanır.

    `bugun` verilmezse yerel (TR) takvim günü kullanılır. Filtresiz bir yol
    BİLEREK YOK: bu fonksiyonun eski hâlinde filtre opsiyoneldi ve hiçbir çağıran
    onu geçmiyordu, yani garanti kâğıt üstündeydi.

    Neden şart: `daily_job` bu adımdan ÖNCE `history.update_recent`'ı çağırıyor;
    o da yfinance ∩ EVDS kesişimini yazıyor ve HER İKİ kaynak da hafta içi
    aynı-gün satırını döndürüyor (2026-07-24 17:25Z koşumunda ölçüldü: GC=F ve
    TP.DK.USD.S.YTL ikisi de 07-24'ü içeriyordu). Filtresiz MAX(date) o gün
    15:35 UTC'de HENÜZ KAPANMAMIŞ bir barı `asof` yapardı; özellikler yarım
    bardan üretilip `predictions`'a DEĞİŞTİRİLEMEZ yazılır, ertesi gün aynı satır
    gerçek kapanışla ezilirdi (INSERT OR REPLACE) → kayıtlı hüküm bir daha asla
    yeniden üretilemez, ADR #007-G'nin "canlı = replay" garantisi düşerdi.
    """
    bugun = bugun or util.local_today()
    r = con.execute("SELECT MAX(date) d FROM history_daily "
                    "WHERE gram_teorik IS NOT NULL AND date < ?",
                    (bugun,)).fetchone()
    return r["d"] if r else None


def feature_vector(cfg: dict, con, asof_date: str) -> dict:
    """`asof_date`te BİLİNEBİLECEK her şey. Sonrasına ait tek satır okunmaz.

    Canlı üretim de tarihsel replay de burayı çağırır — bu, look-ahead'in
    yapısal imkânsızlığının tek garantisidir. Yeni bir özellik eklenecekse
    BURAYA eklenir; başka yerden veri okuyan bir karar yolu açılırsa garanti
    düşer.
    """
    ev = cfg["sources"]["evds"]["series"]
    gecikme = cfg["karar"]["evds_yayin_gecikme_gun"]
    stopaj = cfg["sources"]["evds"].get("mevduat_stopaj_pct", 15.0)
    f: dict = {"asof_date": asof_date}

    # ---- Fiyat serileri (history_daily; gram için YALNIZ kapanış) ----
    _, gram_s = _asof_seri(
        con, "SELECT date, gram_teorik FROM history_daily WHERE gram_teorik "
             "IS NOT NULL AND date <= ? ORDER BY date", (asof_date,))
    _, ons_s = _asof_seri(
        con, "SELECT date, ons_usd FROM history_daily WHERE ons_usd IS NOT NULL "
             "AND date <= ? ORDER BY date", (asof_date,))
    _, kur_s = _asof_seri(
        con, "SELECT date, usdtry FROM history_daily WHERE usdtry IS NOT NULL "
             "AND date <= ? ORDER BY date", (asof_date,))
    f["n_gun"] = len(gram_s)
    f["gram_teorik"] = gram_s[-1] if gram_s else None
    f["ons_usd"] = ons_s[-1] if ons_s else None
    f["usdtry"] = kur_s[-1] if kur_s else None

    # ---- Momentum: literatürdeki en sağlam anomali; 10.5 yılda ölçülebilir ----
    for ad, p in MOM_PENCERELERI.items():
        f[f"gram_getiri_{ad}"] = getiri_pct(gram_s, p)
        f[f"ons_getiri_{ad}"] = getiri_pct(ons_s, p)
        f[f"kur_getiri_{ad}"] = getiri_pct(kur_s, p)

    # ---- Ayrıştırma: TL altının İKİ motoru var, hangisi çekiyor? ----
    # Taktik kazancın varyansının ~%91'i TL bacağında (ADR #007). Bu oran,
    # hareketin altın kaynaklı mı kur kaynaklı mı olduğunu tek sayıya indirir.
    o1, k1 = f.get("ons_getiri_1ay"), f.get("kur_getiri_1ay")
    if o1 is not None and k1 is not None:
        top = abs(o1) + abs(k1)
        f["kur_bacagi_payi"] = abs(k1) / top if top else None
    else:
        f["kur_bacagi_payi"] = None

    # ---- Trend konumu ----
    gma = hareketli_ortalama(ons_s, GMA_PENCERE)
    f["ons_gma200"] = gma
    f["ons_gma200_uzaklik_pct"] = (
        (ons_s[-1] / gma - 1.0) * 100.0 if gma and ons_s else None)
    gma_g = hareketli_ortalama(gram_s, GMA_PENCERE)
    f["gram_gma200_uzaklik_pct"] = (
        (gram_s[-1] / gma_g - 1.0) * 100.0 if gma_g and gram_s else None)

    # ---- Oynaklık rejimi (güven ölçekleme + rejim etiketi girdisi) ----
    # DİKKAT — `kur_oynaklik_60g` çok düşük çıkabilir ve bu BUG DEĞİLDİR.
    # Ölçüldü 2026-07-26: %1.42 yıllık, son 60 günün 59'u artı, günlük sd %0.089.
    # TRY=X piyasa verisi de aynı (%1.40) → EVDS fixing artefaktı değil, gerçek
    # bir sürünen kur rejimi. Karşılaştırma: 2018 şoku %43.0 · 2021 KKM %23.9 ·
    # 2023 %15.1. Aynı sebeple `kur_rsi` 99'a dayanır — 59/60 gün artı olan bir
    # seride Wilder RSI'ın matematiksel sonucu budur.
    #
    # BURADA BİR TUZAK VAR ve karar motoru bunu bilmeli: sürünen kur + yüksek
    # mevduat faizi, "sat ve TL'de otur" fikrinin kâğıt üstünde EN CAZİP
    # göründüğü rejimdir. Ölçüm ise tersini söylüyor — 10.5 yılın en kötü iki
    # SAT ayı (gram -33% ve -36%) tam da sürünme biten aylardır. Sürünme
    # yavaşça kazandırır, bitişi bir gecede alır.
    # Bu gözlem bir KURALA dönüştürülmedi: ölçülmemiş bir sinyali hükme sokmak
    # ADR #007'nin yasakladığı şeydir. Özellik olarak kayıt altında, o kadar.
    f["kur_oynaklik_60g"] = yillik_oynaklik_pct(kur_s, VOL_PENCERE)
    f["gram_oynaklik_60g"] = yillik_oynaklik_pct(gram_s, VOL_PENCERE)
    f["ons_oynaklik_60g"] = yillik_oynaklik_pct(ons_s, VOL_PENCERE)

    # ---- Donchian: net, eşiksiz trend konumu ----
    for p in DONCHIAN:
        f[f"ons_donchian_{p}"] = donchian_konum(ons_s, p)
        f[f"gram_donchian_{p}"] = donchian_konum(gram_s, p)

    # ---- Gerçek OHLC göstergeleri (ons & kur; gram'da OHLC YOK) ----
    from . import chart
    gost = cfg["chart"]["gostergeler"]
    for ad, sembol in (("ons", cfg["chart"]["ohlc"]["symbols"]["ons"]),
                       ("kur", cfg["chart"]["ohlc"]["symbols"]["kur"])):
        h, l, c = _ohlc_asof(con, sembol, asof_date)
        if len(c) > gost["atr_window"] + 1:
            a = chart.atr(h, l, c, gost["atr_window"])
            f[f"{ad}_atr"] = a[-1]
            f[f"{ad}_atr_pct"] = (a[-1] / c[-1] * 100.0) if a[-1] and c[-1] else None
        else:
            f[f"{ad}_atr"] = f[f"{ad}_atr_pct"] = None
        f[f"{ad}_rsi"] = (chart.rsi(c, gost["rsi_window"])[-1]
                          if len(c) > gost["rsi_window"] + 1 else None)
    # gram RSI kapanış serisinden meşru (H/L gerektirmez)
    f["gram_rsi"] = (chart.rsi(gram_s, gost["rsi_window"])[-1]
                     if len(gram_s) > gost["rsi_window"] + 1 else None)

    # ---- Makro (EVDS, yayın gecikmesi uygulanmış) ----
    f["mevduat_3ay_brut"] = evds_asof(con, ev["mevduat_3ay"], asof_date,
                                      gecikme["mevduat_3ay"])
    f["mevduat_1yil_brut"] = evds_asof(con, ev["mevduat_1yil"], asof_date,
                                       gecikme["mevduat_1yil"])
    f["politika_faizi"] = evds_asof(con, ev["aofm_politika"], asof_date,
                                    gecikme["aofm_politika"])
    f["enf_bek_12ay"] = evds_asof(con, ev["enf_bek_12ay"], asof_date,
                                  gecikme["enf_bek_12ay"])

    # ---- Kapı değişkeni: reel net mevduat faizi ----
    # evds_job.context ile AYNI formül, ama asof-güvenli ve TÜFE'ye düşmeden.
    # Sebep: TÜFE serisi 7 aydır bayat (STATE backlog) ve sessiz yedeğe düşme
    # replay'de canlıdan farklı davranırdı — kesişim kuralının ihlali olurdu.
    d1, bek = f["mevduat_1yil_brut"], f["enf_bek_12ay"]
    if d1 is not None and bek is not None:
        net = d1 * (1 - stopaj / 100.0)
        f["reel_net_mevduat"] = ((1 + net / 100) / (1 + bek / 100) - 1) * 100
    else:
        f["reel_net_mevduat"] = None
    return f


def eksik_alanlar(f: dict) -> list[str]:
    """None kalan özellikler — veri kalitesi göstergesi (karneye not düşülür)."""
    return sorted(k for k, v in f.items() if v is None)


if __name__ == "__main__":
    import json

    from . import db, util
    util.load_env()
    _cfg = util.load_config()
    _con = db.connect(_cfg)
    _asof = son_kapali_gun(_con)
    _f = feature_vector(_cfg, _con, _asof)
    print(json.dumps(_f, ensure_ascii=False, indent=2))
    print(f"\neksik: {eksik_alanlar(_f)}")
    _con.close()
