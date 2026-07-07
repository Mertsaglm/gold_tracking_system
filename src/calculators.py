"""Bölüm 4 — Net getiri hesaplayıcıları (vergi + maliyet sonrası).

Saf, testli. Aynı altın hareketinde farklı enstrümanların net sonucu ve vade kırılımı.
Ayrıca bilezik başabaş hesaplayıcısı. CLI + Telegram (/net, /bilezik).

Varsayımlar açıkça belirtilir: aynı brüt altın getirisi tüm enstrümanlara uygulanır;
karşılaştırma vergi+maliyet farkını izole eder. Örnek/bilgilendirme amaçlıdır.
"""
from __future__ import annotations

from typing import Optional

from . import util


def _gross_factor(annual_pct: float, months: int) -> float:
    return (1 + annual_pct / 100.0) ** (months / 12.0)


def instrument_net(cfg: dict, name: str, amount: float, months: int,
                   annual_gold_pct: float) -> dict:
    """Bir enstrümanın vergi+maliyet sonrası net değeri (aynı altın hareketinde)."""
    ic = cfg["instrument_costs"]
    g = _gross_factor(annual_gold_pct, months)
    if name == "banka_hesap":
        c = ic["banka_hesap"]
        net = (amount * (1 - c["alis_makas_pct"] / 100) * g
               * (1 - c["satis_makas_pct"] / 100) * (1 - c["bsmv_pct"] / 100))
    elif name == "altin_fonu":
        c = ic["altin_fonu"]
        after_fee = g * (1 - c["yonetim_ucreti_yillik_pct"] / 100 * months / 12)
        gain = amount * after_fee - amount
        taxed_gain = gain * (1 - c["stopaj_pct"] / 100) if gain > 0 else gain
        net = amount + taxed_gain
    elif name == "fiziki_gram":
        c = ic["fiziki_gram"]
        net = amount * g * (1 - c["alis_satis_makas_pct"] / 100)
    elif name == "altins1":
        c = ic["altins1"]
        net = (amount * (1 - c["komisyon_pct"] / 100) * g
               * (1 - c["komisyon_pct"] / 100))
    else:
        raise ValueError(f"bilinmeyen enstrüman: {name}")
    return {"enstruman": name, "net": net, "net_getiri_pct": (net / amount - 1) * 100}


INSTRUMENTS = ["banka_hesap", "altin_fonu", "fiziki_gram", "altins1"]


def compare_instruments(cfg: dict, amount: float, months: int,
                        annual_gold_pct: Optional[float] = None) -> dict:
    if annual_gold_pct is None:
        annual_gold_pct = cfg["instrument_costs"]["varsayilan_altin_getiri_yillik_pct"]
    results = [instrument_net(cfg, n, amount, months, annual_gold_pct) for n in INSTRUMENTS]
    results.sort(key=lambda x: x["net"], reverse=True)
    return {"amount": amount, "months": months, "altin_getiri_yillik_pct": annual_gold_pct,
            "sonuclar": results, "kazanan": results[0]["enstruman"]}


def break_even_month(cfg: dict, amount: float, annual_gold_pct: Optional[float] = None,
                     a: str = "banka_hesap", b: str = "altin_fonu",
                     max_months: int = 120) -> Optional[int]:
    """a ve b'nin net sonucunun yer değiştirdiği ilk ay (kırılım noktası)."""
    if annual_gold_pct is None:
        annual_gold_pct = cfg["instrument_costs"]["varsayilan_altin_getiri_yillik_pct"]
    prev = None
    for m in range(1, max_months + 1):
        na = instrument_net(cfg, a, amount, m, annual_gold_pct)["net"]
        nb = instrument_net(cfg, b, amount, m, annual_gold_pct)["net"]
        sign = na >= nb
        if prev is not None and sign != prev:
            return m
        prev = sign
    return None


def bilezik_basabas(cfg: dict, brut_gram: float, iscilik_pct: float,
                    has_gram_fiyat: float, milyem: float = 0.916) -> dict:
    """22 ayar bilezik: hurda değeri, ödenen toplam, başabaş için gereken gram yükselişi."""
    hurda = brut_gram * milyem * has_gram_fiyat
    odenen = hurda * (1 + iscilik_pct / 100.0)
    # geri satışta işçilik yanar; başabaş için gram fiyatı odenen/hurda oranı kadar yükselmeli
    gerekli_yukselis = (odenen / hurda - 1.0) * 100.0
    return {
        "brut_gram": brut_gram, "milyem": milyem, "has_gram_fiyat": has_gram_fiyat,
        "hurda_deger": hurda, "iscilik_pct": iscilik_pct, "odenen_toplam": odenen,
        "basabas_gereken_gram_yukselis_pct": gerekli_yukselis,
    }


# ---------- Formatlama (CLI / Telegram) ----------
def format_compare(res: dict) -> str:
    L = [f"💰 {res['amount']:.0f}₺ · {res['months']} ay · altın varsayım "
         f"%{res['altin_getiri_yillik_pct']:.0f}/yıl", ""]
    for r in res["sonuclar"]:
        L.append(f"• {r['enstruman']:12s}: {r['net']:,.0f}₺  ({r['net_getiri_pct']:+.1f}%)")
    L.append(f"\nKazanan: {res['kazanan']}")
    return "\n".join(L)


def format_bilezik(r: dict) -> str:
    return (f"💍 Bilezik başabaş\n"
            f"Brüt {r['brut_gram']:.2f}g × {r['milyem']} × {r['has_gram_fiyat']:.0f}₺ "
            f"= hurda {r['hurda_deger']:,.0f}₺\n"
            f"İşçilik %{r['iscilik_pct']:.0f} → ödenen {r['odenen_toplam']:,.0f}₺\n"
            f"Başabaş için gram +%{r['basabas_gereken_gram_yukselis_pct']:.1f} yükselmeli "
            f"(işçilik geri satışta yanar).")


def _latest_has_price(cfg) -> Optional[float]:
    from . import db
    con = db.connect(cfg)
    row = con.execute("SELECT market_has FROM prim_history WHERE market_has IS NOT NULL "
                      "ORDER BY ts_utc DESC LIMIT 1").fetchone()
    con.close()
    return row["market_has"] if row else None


if __name__ == "__main__":
    import sys
    util.load_env()
    cfg = util.load_config()
    args = sys.argv[1:]
    if args and args[0] == "bilezik":
        brut = float(args[1]) if len(args) > 1 else 20.0
        isc = float(args[2]) if len(args) > 2 else 20.0
        price = float(args[3]) if len(args) > 3 else (_latest_has_price(cfg) or 6200.0)
        print(format_bilezik(bilezik_basabas(cfg, brut, isc, price)))
    else:
        amount = float(args[0]) if args else 100000.0
        months = int(args[1]) if len(args) > 1 else 12
        gold = float(args[2]) if len(args) > 2 else None
        res = compare_instruments(cfg, amount, months, gold)
        print(format_compare(res))
        be = break_even_month(cfg, amount, gold)
        print(f"\nBanka hesabı ↔ altın fonu kırılım: "
              f"{be} ay" if be else "\nKırılım yok (biri hep önde).")
