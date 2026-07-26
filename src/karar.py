"""Bölüm 8b — Karar motoru: raporun EN BAŞINDA duran HÜKÜM.

Bu modül projenin duruşunu değiştirir. Eskiden sistem ölçüyor ama hüküm
vermiyordu; kullanıcı haklı olarak "bu proje işimi görmez" dedi. Sorun hedge
dili değildi — **karnesizlikti.**

    "z=1.2, zayıf kanıt, tavsiye değildir"  → dürüst DEĞİL, yükü kullanıcıya atar
    "TUT, çünkü satmanın ölçülen sonucu ayda -1.99% gram ve bugünkü en güçlü
     sinyalim gereken 3.19 puanlık engelin yarısında"  → net VE dürüst,
     çünkü yanlışlanabilir

İKİ KOL üretilir ve bunlar bağımsız değildir — aynı bahsin ucuz ve pahalı
versiyonudur:

  ÇEKİRDEK : aylık düzenli alımı zamanlar. Gidiş-dönüş makası ÖDEMEZ →
             eşiği daima daha düşük → **birincil kol.**
  TAKTİK   : eldeki gramı sat/geri al. ~%1.20 makas öder → aynı bilgi için
             daha pahalı → **doğuştan KAPALI** (config `karar.taktik.aktif`).

Taktik kolun kapısı, prim z-skoru kapısının (`signals.zscore_dry_run`) birebir
aynısıdır: hüküm her gün üretilir ve kaydedilir, ama kapı açılana dek TUT'a
kilitlenir. Sistem "yapamam" demez — "henüz hakkını kazanmadım, şu sayı
görününce söyleyeceğim" der.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import util

log = logging.getLogger("karar")

UYARI = "Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir."

# Çekirdek kol kademeleri: etiket → config'teki çarpan anahtarı
AL_COK, AL, AL_AZ, BEKLE = "AL_COK", "AL", "AL_AZ", "BEKLE"
TUT, SAT_25, SAT_50 = "TUT", "SAT_25", "SAT_50"

_ETIKET = {
    AL_COK: "ÇOK AL", AL: "NORMAL AL", AL_AZ: "AZ AL", BEKLE: "BEKLE",
    TUT: "TUT — satma", SAT_25: "KISMİ SAT %25", SAT_50: "KISMİ SAT %50",
}


# ================= SAF ÇEKİRDEK (testli) =================

def cekirdek_hukum(reel_net_mevduat: Optional[float], esikler: dict) -> dict:
    """Bu ayki alım şiddeti. Gidiş-dönüş makası ödenmez → ucuz kol.

    Kapı değişkeni reel net mevduat faizi: altının fırsat maliyeti. Negatifken
    TL'de durmak pahalıdır (altın lehine); yüksekken mevduat gerçek rakiptir.

    KADEMELER BİLEREK DAR (1.25x / 0.75x). Sebep: bu değişkenin ölçülen kenarı
    t≈1.4 — en iyi aday, ama KANIT DEĞİL. 2x/0.5x gibi agresif bir kademe
    t=1.4'lük bir bulguyla savunulamaz; gürültüyü kredibilite kılığına sokardı.
    Kanıt güçlenirse (Faz E/F) kademe genişletilir, önce değil.
    """
    ust = esikler["kademe_carpani_ust"]
    alt = esikler["kademe_carpani_alt"]
    if reel_net_mevduat is None:
        return {
            "hukum": AL, "carpan": 1.0, "guven": "düşük",
            "gerekce": ["Reel net mevduat faizi hesaplanamadı (EVDS eksik).",
                        "Kademe uygulanmadı — düzenli alım planına dokunma."],
        }
    if reel_net_mevduat < esikler["reel_mevduat_dusuk_pct"]:
        return {
            "hukum": AL_COK, "carpan": ust, "guven": "düşük",
            "gerekce": [
                f"Reel net mevduat %{reel_net_mevduat:+.1f} → negatif: TL'de "
                "beklemenin maliyeti var, altının fırsat maliyeti düşük.",
                f"Bu ayki alımı {ust:.2f}× yap.",
            ],
        }
    if reel_net_mevduat > esikler["reel_mevduat_yuksek_pct"]:
        return {
            "hukum": AL_AZ, "carpan": alt, "guven": "düşük",
            "gerekce": [
                f"Reel net mevduat %{reel_net_mevduat:+.1f} → yüksek: mevduat "
                "gerçek rakip, altının fırsat maliyeti artıyor.",
                f"Bu ayki alımı {alt:.2f}× yap — ama alımı KESME.",
            ],
        }
    return {
        "hukum": AL, "carpan": 1.0, "guven": "düşük",
        "gerekce": [
            f"Reel net mevduat %{reel_net_mevduat:+.1f} → ara bant "
            f"(%{esikler['reel_mevduat_dusuk_pct']:.0f}–"
            f"%{esikler['reel_mevduat_yuksek_pct']:.0f}): ayırt edici sinyal yok.",
            "Düzenli alım planına aynen devam.",
        ],
    }


def taktik_hukum(ufuk_engel: Optional[dict], kapi: dict,
                 emniyet_carpani: float) -> dict:
    """Eldeki gramı satmak mantıklı mı? Pahalı kol — sert kapıya tabi.

    KAPI KAPALIYSA hüküm koşulsuz TUT'tur; en güçlü SAT sinyali bile bunu
    değiştirmez. Bu, kalibre edilmemiş bir kolun canlıda ilk kez ateşlenip
    gerçek para yakmasını engeller.
    """
    if not kapi["acik"]:
        g = [f"SAT kapısı KAPALI — {kapi['gerekce']}"]
        if ufuk_engel:
            g += [
                f"Ölçülen taban: satmanın {ufuk_engel['gun']} günlük gram "
                f"kazancı ortalama %{ufuk_engel['taban_ortalama_pct']:+.2f} "
                f"(N={ufuk_engel['n_bagimsiz']}, SAT kazanma "
                f"%{ufuk_engel['kazanma_pct']:.0f}).",
                f"Kârlı olması için bir sinyalin tabanı "
                f"+{ufuk_engel['taktik_esik_puan']:.2f} puan yenmesi gerek.",
                "Bu eşiği aşan bir sinyal HENÜZ ÖLÇÜLMEDİ.",
            ]
        return {"hukum": TUT, "guven": "yüksek", "kapi_acik": False,
                "beklenen_gram_kazanc_pct": None, "gerekce": g}

    # Kapı açık: beklenen kazanç emniyet çarpanıyla eşiği aşmalı
    if not ufuk_engel:
        return {"hukum": TUT, "guven": "düşük", "kapi_acik": True,
                "beklenen_gram_kazanc_pct": None,
                "gerekce": ["Engel ölçümü yok — güvenli tarafta kal."]}
    beklenen = ufuk_engel.get("beklenen_gram_kazanc_pct")
    gerekli = ufuk_engel["taktik_esik_puan"] * emniyet_carpani
    if beklenen is None or beklenen < gerekli:
        return {
            "hukum": TUT, "guven": "orta", "kapi_acik": True,
            "beklenen_gram_kazanc_pct": beklenen,
            "gerekce": [
                f"Beklenen gram kazancı "
                f"{'hesaplanamadı' if beklenen is None else f'%{beklenen:+.2f}'}"
                f", gereken +{gerekli:.2f}p (eşik × emniyet {emniyet_carpani:.1f}).",
                "Maliyeti aşmayan işlem yapılmaz.",
            ],
        }
    return {
        "hukum": SAT_25, "guven": "orta", "kapi_acik": True,
        "beklenen_gram_kazanc_pct": beklenen,
        "gerekce": [f"Beklenen gram kazancı %{beklenen:+.2f} > gereken "
                    f"+{gerekli:.2f}p.",
                    "Kısmi sat; geri alım tetiği ayrıca izlenir."],
    }


def kapi_durumu(cfg: dict, karne: Optional[dict]) -> dict:
    """Taktik kolun kapısı açık mı? Şart ÖNCEDEN kayıtlıdır, gevşetilmez."""
    t = cfg["karar"]["taktik"]
    if not t.get("aktif", False):
        return {"acik": False,
                "gerekce": (f"config `karar.taktik.aktif: false`. Açılma şartı: "
                            f"canlı karnede ≥{t['kapi_min_cozulmus']} çözülmüş "
                            f"tahmin, gram etkisi > "
                            f"%{t['kapi_min_gram_etkisi_pct']:.1f}, isabet farkı "
                            f"> +{t['kapi_min_isabet_farki_puan']:.0f}p")}
    n = (karne or {}).get("cozulmus", 0)
    if n < t["kapi_min_cozulmus"]:
        return {"acik": False,
                "gerekce": f"canlı karne {n}/{t['kapi_min_cozulmus']} çözülmüş tahmin"}
    if (karne or {}).get("gram_etkisi_pct", 0.0) <= t["kapi_min_gram_etkisi_pct"]:
        return {"acik": False, "gerekce": "karnede gram etkisi pozitif değil"}
    if (karne or {}).get("isabet_farki_puan", 0.0) < t["kapi_min_isabet_farki_puan"]:
        return {"acik": False, "gerekce": "karnede isabet farkı eşiğin altında"}
    return {"acik": True, "gerekce": f"şart sağlandı (N={n})"}


def karar_ver(ozellikler: dict, cfg: dict, engel: Optional[dict],
              karne: Optional[dict] = None) -> dict:
    """İki kolun hükmü. SAF: ağa/DB'ye dokunmaz, girdisi hazır sözlüklerdir."""
    k = cfg["karar"]
    ufuk = k["birincil_ufuk"]
    ufuk_engel = (engel or {}).get("ufuklar", {}).get(ufuk)
    kapi = kapi_durumu(cfg, karne)
    return {
        "ufuk": ufuk,
        "ufuk_gun": k["ufuklar_gun"][ufuk],
        "model_version": k["model_version"],
        "enstruman": k["enstruman"],
        "kapi": kapi,
        "cekirdek": cekirdek_hukum(ozellikler.get("reel_net_mevduat"), k["cekirdek"]),
        "taktik": taktik_hukum(ufuk_engel, kapi,
                               k["taktik"]["maliyet_emniyet_carpani"]),
        "engel": ufuk_engel,
        "uyari": UYARI,
    }


# ================= IO + biçimleme =================

def build_karar(cfg: dict) -> dict:
    """Canlı hüküm: EVDS bağlamı + önbelleklenmiş engel ölçümü."""
    from . import gram
    ozellikler = {}
    try:
        from .evds_job import context as evds_context
        ozellikler["reel_net_mevduat"] = evds_context(cfg).get("reel_net_mevduat")
    except Exception as e:                      # rapor bloğu yine de çıksın
        log.warning("evds baglami alinamadi: %s", e)
    return karar_ver(ozellikler, cfg, gram.engel_oku(cfg), karne=None)


def format_karar_md(k: dict) -> str:
    c, t = k["cekirdek"], k["taktik"]
    kapi_txt = "AÇIK" if k["kapi"]["acik"] else f"KAPALI ({k['kapi']['gerekce']})"
    L = [
        "## 🎯 HÜKÜM", "",
        f"**ÇEKİRDEK ALIM:** {_ETIKET[c['hukum']]}"
        + (f"  ({c['carpan']:.2f}× normal alım)" if c["carpan"] != 1.0 else ""),
        f"**TAKTİK:** {_ETIKET[t['hukum']]}", "",
        f"_Ufuk {k['ufuk']} ({k['ufuk_gun']} gün) · model {k['model_version']} · "
        f"enstrüman `{k['enstruman']}` · SAT kapısı: {kapi_txt}_", "",
        f"**Neden {_ETIKET[c['hukum']].split(' —')[0]} (çekirdek):**",
    ]
    L += [f"- {g}" for g in c["gerekce"]]
    L += ["", f"**Neden {_ETIKET[t['hukum']].split(' —')[0]} (taktik):**"]
    L += [f"- {g}" for g in t["gerekce"]]
    if k.get("engel"):
        e = k["engel"]
        L += ["", f"_Ölçüm tabanı: {e['n_bagimsiz']} bağımsız pencere · en kötü "
              f"tek pencere %{e['en_kotu_pct']:+.1f} · çekirdek eşiği "
              f"+{e['cekirdek_esik_puan']:.2f}p_"]
    L.append("")
    return "\n".join(L)


def main(cfg: dict) -> str:
    from . import logging_setup
    logging_setup.setup("karar", cfg)
    return format_karar_md(build_karar(cfg))


if __name__ == "__main__":
    util.load_env()
    print(main(util.load_config()))
