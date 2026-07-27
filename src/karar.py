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

# `SAT_50` ve `BEKLE` bilerek REZERVE: hiçbir kod yolu şu an üretmiyor.
# SAT_50 `config.yaml karar.taktik.kismi_oranlar`ın ikinci kademesi için,
# BEKLE ise çekirdek kolun alımı kesmesi gerekirse diye ayrıldı — ama ADR #007-C
# çekirdek kolun alımı ASLA kesmemesini kurala bağladı
# (`test_cekirdek_hicbir_zaman_bekle_demez`). Silinmiyorlar ki etiket sözlüğü
# ile hüküm kümesi arasındaki eşleşme bozulmasın.

# "Anahtar hiç yok" ile "anahtar var ama None" ayrımı için sentinel.
_URETICI_YOK = object()


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
                "beklenen_gram_kazanc_pct": None, "beklenen_kaynak": "engel_yok",
                "gerekce": ["Engel ölçümü yok — güvenli tarafta kal."]}
    beklenen = ufuk_engel.get("beklenen_gram_kazanc_pct", _URETICI_YOK)
    gerekli = ufuk_engel["taktik_esik_puan"] * emniyet_carpani

    # ÜRETİCİ YOK ile "eşiğin altında" AYNI ŞEY DEĞİL — ayrılmazsa ilki
    # ikincisi gibi okunur ("bugün sinyal zayıf"), oysa doğrusu "bu kol henüz
    # bağlanmadı". `gram.engel_ozet` bu alanı hiç üretmiyor ve bu bir unutma
    # değil, ÖLÇÜM SONUCU: ADR #007-H'de 458 haftalık asof üzerinde 14 aday
    # tarandı, en iyisi +1.4p (t≈1.4) ile +3.18p eşiğinin yarısında kaldı.
    # Dürüst bir tahminci olmadığı için buraya uydurma bir tahminci KOYULMADI.
    if beklenen is _URETICI_YOK:
        return {
            "hukum": TUT, "guven": "yüksek", "kapi_acik": True,
            "beklenen_gram_kazanc_pct": None, "beklenen_kaynak": "uretici_yok",
            "gerekce": [
                "Beklenen gram kazancı ÜRETİCİSİ BAĞLI DEĞİL — bu kol kapı "
                "açık olsa bile SAT üretemez.",
                f"Sebep unutma değil ölçüm: taranan 14 adayın en iyisi +1.4p, "
                f"gereken +{gerekli:.2f}p (ADR #007-H).",
                "Eşiği aşan bir aday ölçülene kadar hüküm TUT'tur.",
            ],
        }
    if beklenen is None or beklenen < gerekli:
        return {
            "hukum": TUT, "guven": "orta", "kapi_acik": True,
            "beklenen_gram_kazanc_pct": beklenen, "beklenen_kaynak": "olculdu",
            "gerekce": [
                f"Beklenen gram kazancı "
                f"{'hesaplanamadı' if beklenen is None else f'%{beklenen:+.2f}'}"
                f", gereken +{gerekli:.2f}p (eşik × emniyet {emniyet_carpani:.1f}).",
                "Maliyeti aşmayan işlem yapılmaz.",
            ],
        }
    return {
        "hukum": SAT_25, "guven": "orta", "kapi_acik": True,
        "beklenen_gram_kazanc_pct": beklenen, "beklenen_kaynak": "olculdu",
        "gerekce": [f"Beklenen gram kazancı %{beklenen:+.2f} > gereken "
                    f"+{gerekli:.2f}p.",
                    "Kısmi sat; geri alım tetiği ayrıca izlenir."],
    }


def kapi_durumu(cfg: dict, karne: Optional[dict]) -> dict:
    """Taktik kolun kapısı açık mı? Şart ÖNCEDEN kayıtlıdır, gevşetilmez.

    ÖLÇÜLEBİLİRLİK KONTROLÜ (ADR #008) diğer şartlardan ÖNCE gelir: karnede hiç
    SAT hükmü yoksa `gram_etkisi_pct` ve `isabet_farki_puan` yapısal olarak
    0.00'dır ve şartlar "sağlanmadı" diye okunur. Bu, ölçülmüş bir olumsuzluk
    DEĞİL, ölçümün hiç yapılmamış olmasıdır — ikisini aynı cümleyle raporlamak
    Ekim'deki "trade kolu kalıcı kapalı" kararını bir totolojiye dayandırırdı.

    Not: kapı kapalıyken kol yalnız TUT üretir, TUT tabanın kendisidir, dolayısıyla
    karne asla ölçüm içeremez → kapı kendi kendini kilitler. Bu döngü şu an
    KIRILMIŞ değil, yalnız GÖRÜNÜR kılınmıştır; kırmak için gölge kol gerekir
    (ADR #008'de açık iş olarak kayıtlı).
    """
    t = cfg["karar"]["taktik"]
    if not t.get("aktif", False):
        return {"acik": False, "olculebilir": None,
                "gerekce": (f"config `karar.taktik.aktif: false`. Açılma şartı: "
                            f"canlı karnede ≥{t['kapi_min_cozulmus']} çözülmüş "
                            f"tahmin, gram etkisi > "
                            f"%{t['kapi_min_gram_etkisi_pct']:.1f}, isabet farkı "
                            f"> +{t['kapi_min_isabet_farki_puan']:.0f}p")}
    n = (karne or {}).get("cozulmus", 0)
    if n < t["kapi_min_cozulmus"]:
        return {"acik": False, "olculebilir": (karne or {}).get("olculebilir_mi"),
                "gerekce": f"canlı karne {n}/{t['kapi_min_cozulmus']} çözülmüş tahmin"}
    if not (karne or {}).get("olculebilir_mi", False):
        return {
            "acik": False, "olculebilir": False,
            "gerekce": (f"karne ÖLÇÜM İÇERMİYOR — {n} çözülmüş hükmün hiçbiri SAT "
                        "değil, gram etkisi ve isabet farkı yapısal olarak 0.00. "
                        "Şart sağlanmadı DEĞİL, ölçülmedi (ADR #008)"),
        }
    if (karne or {}).get("gram_etkisi_pct", 0.0) <= t["kapi_min_gram_etkisi_pct"]:
        return {"acik": False, "olculebilir": True,
                "gerekce": "karnede gram etkisi pozitif değil"}
    if (karne or {}).get("isabet_farki_puan", 0.0) < t["kapi_min_isabet_farki_puan"]:
        return {"acik": False, "olculebilir": True,
                "gerekce": "karnede isabet farkı eşiğin altında"}
    return {"acik": True, "olculebilir": True, "gerekce": f"şart sağlandı (N={n})"}


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
        # Karne ÇIKTIYA da konur: `format_karar_md` onu okuyor ve eskiden yalnız
        # `build_karar` sonradan iliştiriyordu — yani saf `karar_ver` çıktısı
        # biçimlendiriciyle uyumsuzdu ve karne satırı testlerde sessizce düşüyordu.
        "karne": karne,
        "cekirdek": cekirdek_hukum(ozellikler.get("reel_net_mevduat"), k["cekirdek"]),
        "taktik": taktik_hukum(ufuk_engel, kapi,
                               k["taktik"]["maliyet_emniyet_carpani"]),
        "engel": ufuk_engel,
        "uyari": UYARI,
    }


# ================= IO + biçimleme =================

def build_karar(cfg: dict) -> dict:
    """Canlı hüküm: özellik vektörü + önbelleklenmiş engel ölçümü + canlı karne.

    Özellikler `ozellikler.feature_vector` üzerinden gelir — tahmin kaydıyla
    AYNI yol. İkinci bir okuma yolu açmak, canlı hükmün kaydedilen hükümden
    farklı girdiyle üretilmesi demek olurdu; karne o an anlamını yitirirdi.
    """
    from . import db, gram, ozellikler as oz, tahmin
    ozellikler, k_karne = {}, None
    try:
        con = db.connect(cfg)
        try:
            asof = oz.son_kapali_gun(con)
            if asof:
                ozellikler = oz.feature_vector(cfg, con, asof)
            k_karne = tahmin.karne(cfg, con)
        finally:
            con.close()
    except Exception as e:                      # rapor bloğu yine de çıksın
        log.warning("ozellik/karne okunamadi: %s", e)
    out = karar_ver(ozellikler, cfg, gram.engel_oku(cfg), karne=k_karne)
    out["asof_date"] = ozellikler.get("asof_date")     # karne'yi karar_ver koyuyor
    return out


def format_karar_md(k: dict) -> str:
    c, t = k["cekirdek"], k["taktik"]
    kapi_txt = "AÇIK" if k["kapi"]["acik"] else f"KAPALI ({k['kapi']['gerekce']})"
    L = [
        "## 🎯 HÜKÜM", "",
        f"**ÇEKİRDEK ALIM:** {_ETIKET[c['hukum']]}"
        + (f"  ({c['carpan']:.2f}× normal alım)" if c["carpan"] != 1.0 else ""),
        f"**TAKTİK:** {_ETIKET[t['hukum']]}", "",
        f"_Ufuk {k['ufuk']} ({k['ufuk_gun']} gün) · model {k['model_version']} · "
        f"enstrüman `{k['enstruman']}` · SAT kapısı: {kapi_txt}_",
        # asof gösterilir: hüküm SON TAM KAPANMIŞ güne dayanır, bugüne değil.
        # Rapor 18:35 TR'de çıkıyor ve o saatte GC=F'in bugünkü kapanışı yok.
        (f"_Veri kesimi (asof): {k['asof_date']} — son tam kapanmış gün_"
         if k.get("asof_date") else ""), "",
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
    # Karne satırı: her hüküm kendi sicilini yanında taşır. Sicil yoksa bunu
    # SÖYLEMEK zorunda — sessiz kalmak "sicilim iyi" izlenimi verirdi.
    kn = k.get("karne")
    if kn:
        if kn.get("cozulmus", 0) == 0:
            ilk = kn.get("ilk_cozum_tarihi")
            L += ["", f"_**Karne:** henüz çözülmüş tahmin yok · "
                  f"{kn.get('bekleyen', 0)} tahmin vadesini bekliyor"
                  + (f", ilki ~{ilk}" if ilk else "") + ". Bu hüküm ölçülen "
                  "tarihsel tabana dayanır; canlı isabet iddiası YOK._"]
        elif not kn.get("olculebilir_mi", False):
            # "fark +0.0p · gram etkisi +0.00%" yazmak, ölçülmemiş bir şeyi
            # ölçülmüş göstermek olur — kayıtlı hükümlerin hiçbiri SAT değilse
            # bu iki sayı piyasadan bağımsız olarak sabittir.
            L += ["", f"_**Karne** ({kn['kol']}): {kn['cozulmus']} çözülmüş · "
                  f"isabet %{kn['isabet_pct']:.0f} · **tabana fark ve gram etkisi "
                  "ÖLÇÜLEMİYOR** (hiç SAT hükmü yok → ikisi de yapısal 0.00). "
                  "Bu karneden taktik kapı kararı çıkmaz — ADR #008._"]
        else:
            zayif = "" if kn.get("yeterli_mi") else " ⚠️ölçüm yetersiz"
            L += ["", f"_**Karne** ({kn['kol']}): {kn['cozulmus']} çözülmüş · "
                  f"isabet %{kn['isabet_pct']:.0f} (taban %{kn['taban_pct']:.0f}, "
                  f"fark {kn['isabet_farki_puan']:+.1f}p) · gram etkisi "
                  f"{kn['gram_etkisi_pct']:+.2f}%{zayif}_"]
    L.append("")
    return "\n".join(L)


def main(cfg: dict) -> str:
    from . import logging_setup
    logging_setup.setup("karar", cfg)
    return format_karar_md(build_karar(cfg))


if __name__ == "__main__":
    util.load_env()
    print(main(util.load_config()))
