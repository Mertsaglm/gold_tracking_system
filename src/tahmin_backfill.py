"""Bölüm 8e — Tarihsel tarama: KARNE DEĞİL, ADAY TARAMASI.

## Bu modül ne DEĞİLDİR

10.5 yıllık geçmişe motoru koşturup "işte karnem, %64 isabet" demek cazip ama
**sahtedir.** Sebep basit: bu sistemdeki eşiklerin çoğu bu veriye BAKILARAK
seçildi — `config.yaml` yorumları bunu kendi kendine belgeliyor (ör. chart
kalibrasyonu: "min_dokunus=3 => HİÇ seviye çıkmıyordu"). Eşiği veriye bakıp
seçip sonra aynı veride ölçmek örneklem-içi ölçümdür; `oos_split: 2023-01-01`
bunu düzeltmez çünkü bölme kararı da aynı bakışın ürünüdür.

**Tek gerçek örneklem-dışı kayıt `predictions` tablosunda, `kaynak='canli'`.**
O saat 2026-07-26'da başladı ve zamanla dolacak. Kısayolu yok.

## O halde bu modül ne İŞE YARAR

**Aday elemek.** "Şu gösterge SAT eşiğini aşabilir mi?" sorusuna, canlıda
6 ay beklemeden bir ÜST SINIR verir: örneklem-içi ölçümde bile eşiği
aşamayan bir aday, örneklem-dışında hiç aşamaz. Yani burada bir aday
"geçemedi" demek güçlü ve kalıcı bir sonuçtur; "geçti" demek ise yalnızca
"canlıda denemeye değer" demektir.

Ölçüm disiplini:
  - Özellikler `ozellikler.feature_vector` üzerinden — canlıyla AYNI yol
  - Örtüşmeyen pencere + TÜM fazlar (`gram.phase_matched_baseline`)
  - Her aday tabana karşı FARK olarak raporlanır, mutlak değerle değil
  - Kaç test yapıldığı ve Bonferroni uyarısı zorunlu (`chart.bonferroni_note`)
  - Zayıf N açıkça bayraklanır
"""
from __future__ import annotations

import logging
import math
import statistics
from typing import Callable, Optional

from . import gram, ozellikler as oz, util

log = logging.getLogger("tahmin_backfill")

RAPOR = "gram_aday_taramasi.md"
# `gram_engeli.json` ile AYNI desen: markdown insan için, JSON hüküm satırı için.
# Karar motoru bu dosyadan okur → kademenin kanıt durumu raporda kendi kendini
# tazeler; kodda sabitlenmiş bir "+1.34p" cümlesi tarama yenilenince BAYATLARDI.
TARAMA_CACHE = "data/aday_taramasi.json"

UYARI_BASI = (
    "> ⚠️ **BU BİR KARNE DEĞİLDİR.** Buradaki eşiklerin bir kısmı bu veriye "
    "bakılarak seçildi; ölçüm örneklem-**İÇİ**dir ve gerçek performansı "
    "OLDUĞUNDAN İYİ gösterir. Tek gerçek örneklem-dışı kayıt `predictions` "
    "tablosunda `kaynak='canli'` satırlarındadır.\n>\n"
    "> Bu tablonun tek meşru kullanımı **aday elemektir**: örneklem-içi ölçümde "
    "bile eşiği aşamayan bir aday, canlıda hiç aşamaz."
)


# ================= Aday kuralları (saf, testli) =================
# Her aday özellik vektöründen bir BOOL üretir: "bugün bu koşul geçerli mi?"
# Kural eklemek serbest; ama eklenen her kural test SAYISINI artırır ve
# Bonferroni uyarısını sertleştirir — bedava aday yoktur.

def _ustu(alan: str, esik: float) -> Callable[[dict], Optional[bool]]:
    def f(v: dict):
        x = v.get(alan)
        return None if x is None else x > esik
    return f


def _altinda(alan: str, esik: float) -> Callable[[dict], Optional[bool]]:
    def f(v: dict):
        x = v.get(alan)
        return None if x is None else x < esik
    return f


ADAYLAR: dict[str, Callable[[dict], Optional[bool]]] = {
    # Makro carry — ADR #007'de tabanı yenmeye en yakın çıkan aday
    "reel_mevduat > %10": _ustu("reel_net_mevduat", 10.0),
    "reel_mevduat < 0": _altinda("reel_net_mevduat", 0.0),
    # Aşırılık / ortalamaya dönüş
    "gram RSI > 75": _ustu("gram_rsi", 75.0),
    "gram RSI < 30": _altinda("gram_rsi", 30.0),
    "ons RSI > 75": _ustu("ons_rsi", 75.0),
    # Trend konumu
    "ons 200GMA üstü %15+": _ustu("ons_gma200_uzaklik_pct", 15.0),
    "gram 200GMA üstü %15+": _ustu("gram_gma200_uzaklik_pct", 15.0),
    "ons Donchian55 tepede (>0.95)": _ustu("ons_donchian_55", 0.95),
    "gram Donchian55 tepede (>0.95)": _ustu("gram_donchian_55", 0.95),
    # Momentum
    "gram 3ay momentum > %25": _ustu("gram_getiri_3ay", 25.0),
    "gram 12ay momentum > %60": _ustu("gram_getiri_12ay", 60.0),
    # Oynaklık rejimi — sürünen kur tuzağı (ADR #007-G)
    "kur oynaklık < %5 (sürünme)": _altinda("kur_oynaklik_60g", 5.0),
    "kur oynaklık > %25 (şok)": _ustu("kur_oynaklik_60g", 25.0),
    # Bacak payı: hareket kur kaynaklı mı
    "kur bacağı payı > 0.7": _ustu("kur_bacagi_payi", 0.7),
}


def t_istatistigi(ornek: list[float], taban_ort: float) -> Optional[float]:
    """Örneğin tabandan farkının t değeri. |t| < 2 → kanıt değil."""
    n = len(ornek)
    if n < 3:
        return None
    sd = statistics.stdev(ornek)
    return (statistics.mean(ornek) - taban_ort) / (sd / math.sqrt(n)) if sd else None


# ================= Tarama =================

def tara(cfg: dict, con, adim_gun: int = 5,
         ufuk_ad: Optional[str] = None) -> dict:
    """Haftalık asof'larda özellikleri üret, adayları gram carry'ye karşı ölç."""
    ufuk_ad = ufuk_ad or cfg["karar"]["birincil_ufuk"]
    h = cfg["karar"]["ufuklar_gun"][ufuk_ad]
    stopaj = cfg["sources"]["evds"].get("mevduat_stopaj_pct", 15.0)
    rt = gram.roundtrip_cost_pct(cfg, cfg["karar"]["enstruman"])

    tarihler, fiyatlar = [], []
    for r in con.execute("SELECT date, gram_teorik FROM history_daily "
                         "WHERE gram_teorik IS NOT NULL ORDER BY date").fetchall():
        tarihler.append(r["date"])
        fiyatlar.append(r["gram_teorik"])
    kod = cfg["sources"]["evds"]["series"]["mevduat_3ay"]
    dep = {r["date"]: r["value"] for r in con.execute(
        "SELECT date, value FROM evds_daily WHERE series_code=? AND value IS NOT NULL",
        (kod,)).fetchall()}
    dep_t = sorted(dep)

    def kazanc(i: int, j: int) -> Optional[float]:
        return gram.gram_carry_gain_pct(fiyatlar[i], fiyatlar[j],
                                        gram.asof_faiz(dep_t, dep, tarihler[i]),
                                        j - i, stopaj)

    # Taban: TÜM fazlar üzerinden (faz artefaktı düzeltmeli — ADR #007-E)
    taban = gram.phase_matched_baseline(len(tarihler), h, kazanc)

    # Özellik vektörleri: ilk GMA200 penceresi dolduktan sonra başla
    baslangic = max(252, oz.GMA_PENCERE)
    ornekler: dict[str, list[float]] = {ad: [] for ad in ADAYLAR}
    kullanilan: dict[str, int] = {ad: -1 for ad in ADAYLAR}   # örtüşme takibi
    n_asof = 0
    for i in range(baslangic, len(tarihler) - h - 1, adim_gun):
        v = oz.feature_vector(cfg, con, tarihler[i])
        n_asof += 1
        for ad, kural in ADAYLAR.items():
            if kural(v) is not True:
                continue
            giris = i + 1                       # look-ahead: giriş t+1
            if giris <= kullanilan[ad]:         # önceki pencereyle örtüşüyor
                continue
            cikis = giris + h
            if cikis >= len(tarihler):
                continue
            k = kazanc(giris, cikis)
            if k is not None:
                ornekler[ad].append(k)
                kullanilan[ad] = cikis

    zayif_n = cfg["karar"]["karne"]["zayif_n"]
    # İKİ EŞİK, TEK KAYNAK (`gram.esik_pct`): taktik gidiş-dönüş makasını da
    # öder, çekirdek ödemez. Yalnız taktik eşiğini raporlamak, AÇIK OLAN kolu
    # (çekirdek) ölçüsüz bırakır — bir aday taktikte "❌" görünüp çekirdekte
    # eşiği geçiyor olabilir; o zaman ❌ okuyan kişi yanlış sonuca varır.
    esik_taktik = gram.esik_pct(taban["ortalama"], rt, "taktik")
    esik_cekirdek = gram.esik_pct(taban["ortalama"], rt, "cekirdek")
    sonuc = []
    for ad, orn in ornekler.items():
        if not orn:
            sonuc.append({"aday": ad, "n": 0, "yeterli": False})
            continue
        ort = statistics.mean(orn)
        fark = ort - taban["ortalama"]
        sonuc.append({
            "aday": ad, "n": len(orn), "ortalama": ort, "fark_puan": fark,
            "t": t_istatistigi(orn, taban["ortalama"]),
            "kazanma_pct": sum(1 for x in orn if x > 0) / len(orn) * 100.0,
            "esigi_gecti": fark > esik_taktik,
            "cekirdek_gecti": fark > esik_cekirdek,
            "yeterli": len(orn) >= zayif_n,
        })
    sonuc.sort(key=lambda s: s.get("fark_puan", -999), reverse=True)
    return {
        "ufuk": ufuk_ad, "ufuk_gun": h, "n_asof": n_asof, "n_test": len(ADAYLAR),
        "roundtrip_pct": rt, "taban": taban, "zayif_n": zayif_n,
        "esik_puan": esik_taktik, "esik_cekirdek_puan": esik_cekirdek,
        "ilk": tarihler[baslangic], "son": tarihler[-1],
        "adaylar": sonuc,
    }


def format_tarama_md(cfg: dict, t: dict) -> str:
    from . import chart
    L = [f"# Gram Aday Taraması — {t['ufuk']} ufku", "", UYARI_BASI, "",
         f"_Tarama: {t['ilk']} → {t['son']} · {t['n_asof']} haftalık asof · "
         f"örtüşmeyen pencere · tüm fazlar · gidiş-dönüş %{t['roundtrip_pct']:.2f}_",
         "",
         "## Aşılması gereken eşik", "",
         f"- Taban (SAT'ın koşulsuz gram kazancı): **%{t['taban']['ortalama']:+.2f}** "
         f"(N={t['taban']['n_bagimsiz']} bağımsız pencere)",
         f"- **TAKTİK** kol (sat→geri al, gidiş-dönüş %{t['roundtrip_pct']:.2f} öder): "
         f"tabanı **+{t['esik_puan']:.2f} puan** yenmeli",
         f"- **ÇEKİRDEK** kol (alımı ertele, makas ÖDEMEZ): tabanı "
         f"**+{t['esik_cekirdek_puan']:.2f} puan** yenmeli — bu kol ŞU AN AÇIK",
         "",
         "> Çekirdek eşiği, alımı ertelemenin gram olarak başa baş noktasıdır: "
         "farkı bu kadar yenemeyen bir kural, alımı geciktirdiği her ay "
         "**gram kaybettirir**. Kademe (0.75×) kaybı küçültür, işaretini "
         "değiştirmez.", "",
         "## Adaylar (fark büyükten küçüğe)", "",
         "| Aday | N | Ort. gram kazancı | Tabana fark | t | Kazanma | Taktik | Çekirdek |",
         "|---|---:|---:|---:|---:|---:|:--:|:--:|"]
    for a in t["adaylar"]:
        if not a["n"]:
            L.append(f"| {a['aday']} | 0 | _hiç tetiklenmedi_ | | | | — | — |")
            continue
        zayif = "" if a["yeterli"] else f" ⚠️"
        tv = f"{a['t']:+.2f}" if a["t"] is not None else "—"
        gecti = "✅" if a["esigi_gecti"] else "❌"
        cek = "✅" if a["cekirdek_gecti"] else "❌"
        L.append(f"| {a['aday']} | {a['n']}{zayif} | %{a['ortalama']:+.2f} | "
                 f"**{a['fark_puan']:+.2f}p** | {tv} | %{a['kazanma_pct']:.0f} | "
                 f"{gecti} | {cek} |")

    gecen = [a for a in t["adaylar"] if a.get("esigi_gecti")]
    guclu = [a for a in gecen if a.get("yeterli") and a.get("t")
             and abs(a["t"]) >= 2.0]
    cek_gecen = [a for a in t["adaylar"] if a.get("cekirdek_gecti")]
    cek_guclu = [a for a in cek_gecen if a.get("yeterli") and a.get("t")
                 and abs(a["t"]) >= 2.0]
    L += ["", f"_⚠️ = N < {t['zayif_n']}, ölçüm yetersiz._", "",
          "## Çekirdek kolun hükmü (AÇIK OLAN kol)", ""]
    if not cek_gecen:
        L += ["**Hiçbir aday çekirdek eşiğini de geçmedi.** Yani bugün alımı "
              "erteleten hiçbir kuralın ölçülmüş bir gerekçesi yok."]
    elif not cek_guclu:
        L += [f"**{len(cek_gecen)} aday çekirdek eşiğini geçti ama hiçbiri güçlü "
              f"değil** (|t| ≥ 2 ve N ≥ {t['zayif_n']} yok):", ""]
        L += [f"- `{a['aday']}` — fark {a['fark_puan']:+.2f}p, "
              f"t={(f'{a['t']:+.2f}' if a['t'] is not None else '—')}, N={a['n']}"
              for a in cek_gecen]
    else:
        L += [f"**{len(cek_guclu)} aday hem çekirdek eşiğini geçti hem |t| ≥ 2:**", ""]
        L += [f"- `{a['aday']}` — fark {a['fark_puan']:+.2f}p, t={a['t']:+.2f}, "
              f"N={a['n']}" for a in cek_guclu]
    L += ["", "## Taktik kolun hükmü", ""]
    if not gecen:
        L += ["**Hiçbir aday eşiği geçmedi.** Örneklem-içi ölçümde bile "
              "aşılamayan bir eşik, canlıda hiç aşılmaz. Taktik kol kapalı "
              "kalmalı; yeni aday aranmadan SAT açılmamalı."]
    elif not guclu:
        L += [f"**{len(gecen)} aday eşiği geçti ama hiçbiri güçlü değil** "
              f"(|t| ≥ 2 ve N ≥ {t['zayif_n']} şartını sağlayan yok). "
              "Örneklem-içi ölçümde zayıf olan, örneklem-dışında yok demektir."]
    else:
        L += [f"**{len(guclu)} aday hem eşiği geçti hem |t| ≥ 2:**", ""]
        L += [f"- `{a['aday']}` — fark {a['fark_puan']:+.2f}p, t={a['t']:+.2f}, "
              f"N={a['n']}" for a in guclu]
        L += ["", "Bunlar **canlıda denemeye değer** demektir, 'çalışıyor' "
              "demek DEĞİL. Karar canlı karneden verilir."]
    L += ["", f"> {chart.bonferroni_note(t['n_test'])}", "",
          "---", "_Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir._"]
    return "\n".join(L)


def tarama_ozeti(t: dict) -> dict:
    """Hüküm satırının okuyacağı küçük özet — tam tarama JSON'a sığmaz, gerekmez."""
    return {
        "ufuk": t["ufuk"], "ilk": t["ilk"], "son": t["son"],
        "esik_cekirdek_puan": t["esik_cekirdek_puan"],
        "esik_taktik_puan": t["esik_puan"],
        "n_test": t["n_test"], "zayif_n": t["zayif_n"],
        # ADA GÖRE indeks: karar motoru kademeyi ÜRETEN kuralı adıyla arar
        # (`karar.cekirdek_hukum` → "kural"). Liste olsaydı hangi adayın
        # kademeyi doğurduğu kaybolurdu ve rapor başka bir adayın karnesini
        # gösterirdi — ölçüm gibi görünen bir yanlış.
        "adaylar": {
            a["aday"]: {"fark_puan": a["fark_puan"], "n": a["n"], "t": a["t"],
                        "yeterli": a["yeterli"],
                        "cekirdek_gecti": a["cekirdek_gecti"],
                        "taktik_gecti": a["esigi_gecti"]}
            for a in t["adaylar"] if a.get("n")},
        "cekirdek_gecen": [a["aday"] for a in t["adaylar"]
                           if a.get("cekirdek_gecti")],
    }


def tarama_oku(cfg: dict) -> Optional[dict]:
    """Önbelleklenmiş tarama özeti; yoksa None (hüküm satırı sessizce düşer)."""
    return util.read_json(util.abspath(TARAMA_CACHE), None)


def run(cfg: dict, ufuk_ad: Optional[str] = None) -> str:
    from . import db, logging_setup
    logging_setup.setup("tahmin_backfill", cfg)
    con = db.connect(cfg)
    try:
        t = tara(cfg, con, ufuk_ad=ufuk_ad)
    finally:
        con.close()
    path = util.abspath(f"{cfg['paths']['reports_dir']}/{RAPOR}")
    path.write_text(format_tarama_md(cfg, t), encoding="utf-8")
    util.write_json(util.abspath(TARAMA_CACHE), tarama_ozeti(t))
    log.info("aday taramasi yazildi: %s (+ %s)", path, TARAMA_CACHE)
    return str(path)


if __name__ == "__main__":
    import sys
    util.load_env()
    print(run(util.load_config(), sys.argv[1] if len(sys.argv) > 1 else None))
