"""Hesap katmanı: teorik gram, prim, makas, çeyrek primi, dekompozisyon, z-skor.

Tüm fonksiyonlar saftır (yan etkisiz) — birim testlerinin hedefi budur.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Optional, Sequence

TROY_OZ = 31.1034768


def theoretical_gram(ons_usd: float, usdtry: float, troy: float = TROY_OZ) -> float:
    """Teorik has (saf, 1000/1000) gram TL fiyatı."""
    return ons_usd / troy * usdtry


def prim_pct(market_price: float, theoretical: float) -> float:
    """Piyasa fiyatının teorik değerden yüzde sapması (prim/iskonto)."""
    return (market_price / theoretical - 1.0) * 100.0


def bagimsizlik_cv(oranlar: Sequence[float]) -> Optional[float]:
    """Piyasa/teorik oranının değişim katsayısı (sd/ort) — BAĞIMSIZLIK ÖLÇÜSÜ.

    Prim, tanım gereği İKİ BAĞIMSIZ fiyatın farkıdır. Eğer satıcı gram fiyatını
    kendi ons ve kur alanlarından TÜRETİYORSA oran cebirsel bir sabite çöker ve
    "prim" artık piyasayı değil satıcının kendi çarpanını ölçer.

    Oran, iki bacağı da AYNI satıcıdan alarak hesaplanmalıdır; araya farklı bir
    kur beslemesi girerse onun gürültüsü kimliği maskeler (ölçüldü 2026-08-28:
    saf Truncgil tabanında gün-içi sd 1.7e-05, araya yfinance kuru girince
    4.9e-04 — 29 kat).

    Değişim katsayısı kullanılır ki saflık çarpanı (995/1000) sadeleşsin ve
    eşik ölçek-bağımsız kalsın.
    """
    if len(oranlar) < 2:
        return None
    ort = mean(oranlar)
    if ort == 0:
        return None
    return pstdev(oranlar) / abs(ort)


def turetilmis_mi(oranlar: Sequence[float], esik: float,
                  min_kayit: int) -> Optional[bool]:
    """Piyasa bacağı teorik bacaktan türetilmiş mi? None = hüküm verilemez.

    EŞİĞİN DAYANAĞI (ölçüldü 2026-08-28, 934 arşiv kaydı, iki rejim):
      - gerçek ölçüm rejimi (07-07…08-16, hafta içi, N=29 gün): en düşük CV
        2.97e-04, medyan 5.57e-04
      - kimlik rejimi (08-17…08-28, N=8 gün): en yüksek CV 5.50e-05,
        medyan 1.66e-05
      İki küme ÖRTÜŞMÜYOR; aradaki boşluk 5.4 kat, geometrik ortası 1.28e-04.
      Yuvarlama gürültüsü tabanı (2 ondalık gram + 4 ondalık kur) ~2.2e-06.
    Yani 1e-04 eşiği tabanın ~45 katı, en küçük gerçek ölçümün ~3'te biri —
    iki rejim arasındaki boşluğa oturuyor, veriye UYDURULMADI.

    `min_kayit`: gün-içi sd az kayıtla anlamsızdır. Actions ritmi düştüğünde
    (ölçüldü 2026-08-27/28: 2 kayıt/gün) hüküm verilemez → None döner ve
    çağıran taraf komşu günün hükmünü taşır.
    """
    if len(oranlar) < min_kayit:
        return None
    cv = bagimsizlik_cv(oranlar)
    if cv is None:
        return None
    return cv < esik


def spread_pct(buying: float, selling: float) -> float:
    """Alış-satış makası, orta fiyata oran (%)."""
    mid = (buying + selling) / 2.0
    if mid == 0:
        return 0.0
    return (selling - buying) / mid * 100.0


def quarter_prim_pct(
    coin_sell: float,
    gram_has_sell: float,
    gross_g: float,
    milyem: float,
) -> float:
    """Ziynet altının (çeyrek/tam...) has içeriğine göre primi (%).

    fair = has_içerik(gram) * has_gram_fiyatı ; prim = coin_sell/fair - 1.
    gram_has_sell saf (1000) bazında olmalı.
    """
    has_content_g = gross_g * milyem
    fair = has_content_g * gram_has_sell
    if fair == 0:
        return 0.0
    return (coin_sell / fair - 1.0) * 100.0


@dataclass
class Decomposition:
    ons_pct: float
    kur_pct: float
    prim_pct: float
    total_pct: float


def decompose(
    ons0: float, usd0: float, prim0_pct: float,
    ons1: float, usd1: float, prim1_pct: float,
) -> Decomposition:
    """Gram TL log-getirisini ons / kur / prim bileşenlerine ayırır.

    Δln(gram) = Δln(ons) + Δln(kur) + Δln(1+prim). Bileşenler TAM toplanır.
    """
    d_ons = math.log(ons1 / ons0)
    d_kur = math.log(usd1 / usd0)
    d_prim = math.log((1.0 + prim1_pct / 100.0) / (1.0 + prim0_pct / 100.0))
    total = d_ons + d_kur + d_prim
    return Decomposition(
        ons_pct=d_ons * 100.0,
        kur_pct=d_kur * 100.0,
        prim_pct=d_prim * 100.0,
        total_pct=total * 100.0,
    )


@dataclass
class ZResult:
    value: Optional[float]
    status: str          # "ok" | "insufficient" | "flat"
    n: int
    mean: Optional[float] = None
    std: Optional[float] = None


def zscore(history: Sequence[float], value: float, min_samples: int = 60) -> ZResult:
    """Genişleyen pencere z-skoru. Yetersiz örnekte value=None, status='insufficient'."""
    n = len(history)
    if n < min_samples:
        return ZResult(value=None, status="insufficient", n=n)
    mu = mean(history)
    sd = pstdev(history)
    if sd == 0:
        return ZResult(value=None, status="flat", n=n, mean=mu, std=sd)
    return ZResult(value=(value - mu) / sd, status="ok", n=n, mean=mu, std=sd)


def gram_from_theoretical(theoretical: float, prim_pct_val: float) -> float:
    """Prim ile teorikten piyasa gram fiyatı (dekompozisyon tutarlılık testi için)."""
    return theoretical * (1.0 + prim_pct_val / 100.0)
