"""Bölüm 8a — Gram hakemi: her hükmün ölçüldüğü ortak yardımçubuğu.

AMAÇ FONKSİYONU: **terminal gram sayısı**. TL getirisi DEĞİL.

Neden: kullanıcı her ay düzenli altın alıyor ve "elimdeki gramı artırmalıyım"
diyor. Ölçüt gram olunca TL enflasyonu artefaktı kendiliğinden ölür (backtest.py
`_regime_stats_table` bunun için tabandan-fark sunmak zorunda kalıyor) ve her
iddia yanlışlanabilir hale gelir: 100 gramla başladın, 108 gram bitirdin → tuttu.

Bu modülün cevapladığı tek soru şudur:
    "Bugün satıp mevduatta bekleyip sonra geri alırsam GRAM sayım artar mı?"

Cevap üç şeye bağlı ve üçü de burada hesaplanır:
  1. fiyat oranı  (giriş/çıkış)   — düşerse gram kazanırsın
  2. mevduat carry (bekleme faizi) — TL'de beklerken kazandığın, ŞART: onsuz
     ölçüm SAT'ı haksız yere kötü gösterir
  3. gidiş-dönüş maliyeti          — İş Bankası makası + BSMV, kazancı yer

SAF ve testlidir; ağa/DB'ye dokunmaz (IO aşağıda ayrı bölümde).
"""
from __future__ import annotations

import logging
import statistics
from typing import Callable, Iterator, Optional, Sequence

from . import util

log = logging.getLogger("gram")


# ================= SAF ÇEKİRDEK (testli) =================

def roundtrip_cost_pct(cfg: dict, enstruman: str = "banka_hesap") -> float:
    """Bir gidiş-dönüşün (sat + geri al) maliyeti, yüzde.

    TEK KAYNAK: `calculators.instrument_net`. Maliyet formülünü burada tekrar
    yazmıyoruz — eşik mantığının iki yerde tutulup sessizce ayrışması bu repoda
    bir kez yaşandı (bkz. `signals.evaluate_alerts` docstring'i, 5 kural vs 3).

    Fiyat hareketi sıfır (annual_gold_pct=0) ve süre sıfır (months=0) verilir →
    geriye yalnız makas/komisyon/vergi kalır.

    NOT: `altin_fonu` için 0 döner ve bu DOĞRUDUR — fonun maliyeti giriş-çıkış
    makası değil, zamana yayılı yönetim ücretidir. Gidiş-dönüş kavramı ona
    uymaz; taktik kol için fon kullanılacaksa maliyet ayrıca modellenmeli.
    """
    from . import calculators
    r = calculators.instrument_net(cfg, enstruman, amount=1.0, months=0,
                                   annual_gold_pct=0.0)
    return -r["net_getiri_pct"]


def net_mevduat_faizi(brut_yillik_pct: float, stopaj_pct: float, gun: int) -> float:
    """`gun` günlük dönem için net (stopaj sonrası) mevduat getirisi, oran (yüzde DEĞİL)."""
    return (brut_yillik_pct * (1 - stopaj_pct / 100.0) / 100.0) * gun / 365.0


def gram_carry_gain_pct(giris_gram_fiyat: float, cikis_gram_fiyat: float,
                        mevduat_yillik_brut_pct: Optional[float], gun: int,
                        stopaj_pct: float) -> Optional[float]:
    """SAT → mevduatta bekle → geri al işleminin GRAM kazancı, yüzde.

    1 gram sat → `giris_gram_fiyat` TL al → `gun` gün mevduatta işlet →
    `cikis_gram_fiyat`'tan geri al → kaç gram oldun?

        gram_sonra = giris/cikis × (1 + net_faiz)

    TL enflasyonu bu orandan DÜŞER: pay ve payda ikisi de TL cinsindendir.
    Ölçtüğün şey saf gram, satın alma gücü değil — kullanıcının amacı bu.

    Mevduat faizi ŞARTTIR, ihmal edilemez: onsuz ölçüm SAT'ı ~0.8 puan
    (1 ay ufkunda) haksız yere kötü gösterir.
    """
    if not giris_gram_fiyat or not cikis_gram_fiyat:
        return None
    faiz = 0.0
    if mevduat_yillik_brut_pct is not None:
        faiz = net_mevduat_faizi(mevduat_yillik_brut_pct, stopaj_pct, gun)
    return ((giris_gram_fiyat / cikis_gram_fiyat) * (1 + faiz) - 1.0) * 100.0


def hukum_dogru_mu(hukum: str, gram_carry_kazanc_pct: Optional[float],
                   roundtrip_pct: float) -> Optional[bool]:
    """Bir hükmün gram uzayında doğru çıkıp çıkmadığı.

    Üç bölge var ve ortadaki bölge kritik:
      kazanç > maliyet   → SAT haklıydı VE masrafını çıkardı  → SAT doğru
      0 < kazanç < mal.  → SAT haklıydı ama masrafını ÇIKARMADI → TUT doğru
      kazanç < 0         → satmak gram kaybettirirdi          → AL/TUT doğru

    ATR ölü bandı KULLANILMAZ. Sebep: ayarlanabilir bir eşik, karneyi
    güzelleştirmek için oynanabilir bir kol demektir. Buradaki tek eşik
    (gidiş-dönüş maliyeti) piyasadan gelir, bizim seçimimiz değildir.

    Sıfır noktası da fiyat sabitliği DEĞİL, carry-nötr noktadır: gram fiyatı
    yatay kaldığı ay bile mevduat faizi yüzünden SAT kazanmıştır.

    ⚠️ DİKKAT — bunun karne üzerindeki doğrudan sonucu: `SAT*` OLMAYAN her hüküm
    (`AL_*`, `TUT`, `BEKLE`) burada tıpatıp `TUT` ile aynı cevabı alır. Yani
    kayıtlı hükümler arasında hiç `SAT*` yoksa "tabana fark" ÖZDEŞ olarak 0
    çıkar; bu bir ölçüm değil, fonksiyonun tanımının sonucudur. Karne bunu
    `olculebilir_mi` bayrağıyla ayırt eder (`tahmin.karne_ozeti`, ADR #008).
    """
    if gram_carry_kazanc_pct is None:
        return None
    sat_kazandi = gram_carry_kazanc_pct > roundtrip_pct
    if hukum.startswith("SAT"):
        return sat_kazandi
    # AL_* / TUT / BEKLE: satmamak doğruysa doğru
    return not sat_kazandi


def esik_pct(taban_ort_pct: float, roundtrip_pct: float, kol: str) -> float:
    """Bir sinyalin kârlı olması için tabanı kaç PUAN yenmesi gerektiği.

    kol='taktik'   → |taban| + gidiş-dönüş  (hem sürüklenmeyi hem makası yenmeli)
    kol='cekirdek' → |taban|                (alımı ertelemek makas ödemez)

    Çekirdek kolun eşiği daima daha düşüktür; aynı bilgiyi ucuza kullanmanın yolu
    budur. İki kol bağımsız değil, aynı bahsin ucuz ve pahalı versiyonudur.
    """
    return abs(taban_ort_pct) + (roundtrip_pct if kol == "taktik" else 0.0)


def nonoverlap_windows(n: int, horizon: int, faz: int = 0) -> Iterator[tuple[int, int]]:
    """`faz`'dan başlayan örtüşmeyen (giris_idx, cikis_idx) pencereleri."""
    i = faz
    while i + horizon < n:
        yield i, i + horizon
        i += horizon


def phase_matched_baseline(n: int, horizon: int,
                           deger_fn: Callable[[int, int], Optional[float]]) -> dict:
    """Örtüşmeyen pencere ölçümünü TÜM fazlar üzerinden yapar.

    NEDEN VAR — mevcut kodda gerçek bir metodoloji hatasının düzeltmesi:
    `chart.measure_edge` tabanı `range(len(closes))` ile 0. indeksten başlatıyor,
    sinyal kümesi ise başka bir fazdan geliyor. Ölçüldü (2026-07-26): h=63'te
    yalnız faz seçimi tabanı ons'ta 2.64, gram TL'de 3.23 puan oynatıyor.
    `config.yaml chart.dogrulama.min_anlamli_fark_puan: 1.0` bu gürültünün
    ALTINDA → tek fazlı ölçümün "zayıf kanıt" bulguları faz artefaktından
    ayırt edilemez.

    Döner: faz_0 (eski tek-fazlı ölçüm, karşılaştırma için), ortalama (faz
    ortalamalarının ortalaması = tarafsız kestirim), yayilim (artefaktın
    büyüklüğü), ve havuzlanmış dağılım.
    """
    faz_ortalamalari = []
    havuz: list[float] = []
    faz0: list[float] = []
    for faz in range(max(1, horizon)):
        vals = [v for v in (deger_fn(i, j)
                            for i, j in nonoverlap_windows(n, horizon, faz))
                if v is not None]
        if not vals:
            continue
        if faz == 0:
            faz0 = vals
        faz_ortalamalari.append(statistics.mean(vals))
        havuz.extend(vals)
    if not havuz:
        return {"n_bagimsiz": 0, "yeterli": False}
    return {
        # N: bir fazdaki bağımsız pencere sayısı. Havuz N'i horizon kat şişkindir
        # ve BAĞIMSIZ DEĞİLDİR — istatistiksel güç bu sayıdan okunur.
        "n_bagimsiz": len(faz0) or (len(havuz) // max(1, horizon)),
        "n_havuz": len(havuz),
        "faz_0_ortalama": statistics.mean(faz0) if faz0 else None,
        "ortalama": statistics.mean(faz_ortalamalari),
        "medyan": statistics.median(havuz),
        "yayilim": (max(faz_ortalamalari) - min(faz_ortalamalari)
                    if len(faz_ortalamalari) > 1 else 0.0),
        "kazanma_pct": sum(1 for x in havuz if x > 0) / len(havuz) * 100.0,
        "en_kotu": min(havuz),
        "en_iyi": max(havuz),
        "yeterli": True,
    }


# ================= IO: ölçüm koşumu =================

def _seriler(cfg: dict, con) -> tuple[list[tuple[str, float]], dict]:
    """(history_daily gram serisi, mevduat faizi {tarih: brüt yıllık}) döner."""
    kod = cfg["sources"]["evds"]["series"]["mevduat_3ay"]
    rows = con.execute(
        "SELECT date, gram_teorik FROM history_daily "
        "WHERE gram_teorik IS NOT NULL ORDER BY date").fetchall()
    dep = {r["date"]: r["value"] for r in con.execute(
        "SELECT date, value FROM evds_daily WHERE series_code=? AND value IS NOT NULL "
        "ORDER BY date", (kod,)).fetchall()}
    return [(r["date"], r["gram_teorik"]) for r in rows], dep


def asof_faiz(dep_tarihleri: Sequence[str], dep: dict, tarih: str) -> Optional[float]:
    """`tarih`te BİLİNEN son mevduat faizi. Sonrasına asla bakmaz (look-ahead)."""
    import bisect
    i = bisect.bisect_right(dep_tarihleri, tarih)
    return dep[dep_tarihleri[i - 1]] if i else None


def sat_engeli(cfg: dict, con, ufuklar: Optional[dict] = None) -> dict:
    """"Satmak gram kazandırır mı?" sorusunun tam ölçümü.

    Her ufuk için: örtüşmeyen pencerelerde SAT→mevduat→geri al'ın gram kazancı,
    tüm fazlar üzerinden (faz artefaktı düzeltmeli).
    """
    ufuklar = ufuklar or cfg["karar"]["ufuklar_gun"]
    stopaj = cfg["sources"]["evds"].get("mevduat_stopaj_pct", 15.0)
    seri, dep = _seriler(cfg, con)
    dep_t = sorted(dep)
    tarihler = [d for d, _ in seri]
    fiyatlar = [p for _, p in seri]
    n = len(seri)

    def yap(i: int, j: int) -> Optional[float]:
        return gram_carry_gain_pct(fiyatlar[i], fiyatlar[j],
                                   asof_faiz(dep_t, dep, tarihler[i]),
                                   j - i, stopaj)

    out = {"n_gun": n, "ilk": tarihler[0] if n else None,
           "son": tarihler[-1] if n else None, "ufuklar": {}}
    for ad, h in ufuklar.items():
        s = phase_matched_baseline(n, h, yap)
        if s.get("yeterli"):
            # Maliyet sonrası: kaç pencerede SAT gerçekten masrafını çıkardı
            rt = roundtrip_cost_pct(cfg, cfg["karar"]["enstruman"])
            vals = [v for faz in range(h)
                    for v in (yap(i, j) for i, j in nonoverlap_windows(n, h, faz))
                    if v is not None]
            s["maliyet_sonrasi_kazanma_pct"] = (
                sum(1 for v in vals if v > rt) / len(vals) * 100.0)
        s["gun"] = h
        out["ufuklar"][ad] = s
    return out


def alt_donem_kirilimi(cfg: dict, con, horizon: int,
                       donemler: Sequence[tuple[str, str, str]]) -> list[dict]:
    """Ölçüm bir dönem artefaktı mı, yapısal mı? Alt dönemlerde işaret aynı mı?"""
    stopaj = cfg["sources"]["evds"].get("mevduat_stopaj_pct", 15.0)
    seri, dep = _seriler(cfg, con)
    dep_t = sorted(dep)
    out = []
    for ad, lo, hi in donemler:
        vals = []
        for faz in range(horizon):
            for i, j in nonoverlap_windows(len(seri), horizon, faz):
                if not (lo <= seri[i][0] <= hi):
                    continue
                v = gram_carry_gain_pct(seri[i][1], seri[j][1],
                                        asof_faiz(dep_t, dep, seri[i][0]),
                                        j - i, stopaj)
                if v is not None:
                    vals.append(v)
        if vals:
            out.append({"donem": ad, "n": len(vals) // horizon,
                        "ortalama": statistics.mean(vals),
                        "kazanma_pct": sum(1 for x in vals if x > 0) / len(vals) * 100.0})
    return out


# ================= Rapor =================

def format_engel_md(cfg: dict, engel: dict, kirilim: list[dict]) -> str:
    rt_ana = roundtrip_cost_pct(cfg, cfg["karar"]["enstruman"])
    L = [
        "# Gram Engeli — \"satmak gram kazandırır mı?\"", "",
        f"_Ölçüm: {engel['ilk']} → {engel['son']} · {engel['n_gun']} gün · "
        f"örtüşmeyen pencere · mevduat carry dahil (TP.TRY.MT03, stopaj "
        f"%{cfg['sources']['evds'].get('mevduat_stopaj_pct', 15.0):.0f}) · "
        "tüm fazlar üzerinden_", "",
        "Ölçülen büyüklük: **1 gram sat → TL'yi mevduatta beklet → geri al →"
        " kaç gram oldun?**", "",
        "## Gidiş-dönüş maliyetleri", "",
        "| Enstrüman | Gidiş-dönüş | Kaynak |", "|---|---:|---|",
    ]
    for ens in ("banka_hesap", "altins1", "fiziki_gram"):
        try:
            L.append(f"| `{ens}` | %{roundtrip_cost_pct(cfg, ens):.2f} | "
                     f"`calculators.instrument_net` |")
        except Exception:
            continue
    L += ["", "_`altin_fonu` listede yok: maliyeti gidiş-dönüş makası değil, "
          "zamana yayılı yönetim ücretidir._", "",
          "## Ufuk bazında ölçüm", "",
          "| Ufuk | Gün | N (bağımsız) | SAT gram kazancı (ort) | Medyan | "
          "SAT kazanır | Maliyet sonrası | En kötü |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for ad, s in engel["ufuklar"].items():
        if not s.get("yeterli"):
            L.append(f"| {ad} | {s['gun']} | — | _yetersiz veri_ | | | | |")
            continue
        L.append(f"| {ad} | {s['gun']} | {s['n_bagimsiz']} | "
                 f"**{s['ortalama']:+.2f}%** | {s['medyan']:+.2f}% | "
                 f"%{s['kazanma_pct']:.0f} | %{s['maliyet_sonrasi_kazanma_pct']:.0f} | "
                 f"{s['en_kotu']:+.1f}% |")

    L += ["", "## Sinyalin yenmesi gereken engel", "",
          "| Ufuk | Taban | TAKTİK eşiği (SAT) | ÇEKİRDEK eşiği (az al) |",
          "|---|---:|---:|---:|"]
    for ad, s in engel["ufuklar"].items():
        if not s.get("yeterli"):
            continue
        L.append(f"| {ad} | {s['ortalama']:+.2f}% | "
                 f"**+{esik_pct(s['ortalama'], rt_ana, 'taktik'):.2f}p** | "
                 f"+{esik_pct(s['ortalama'], rt_ana, 'cekirdek'):.2f}p |")
    L += ["", f"_Taktik eşiği = |taban| + gidiş-dönüş (%{rt_ana:.2f}); çekirdek "
          "eşiği makas ödemez._", ""]

    if kirilim:
        L += ["## Alt dönem kırılımı — artefakt mı, yapısal mı?", "",
              "| Dönem | N | SAT gram kazancı (ort) | SAT kazanır |",
              "|---|---:|---:|---:|"]
        for k in kirilim:
            L.append(f"| {k['donem']} | {k['n']} | {k['ortalama']:+.2f}% | "
                     f"%{k['kazanma_pct']:.0f} |")
        isaretler = {k["ortalama"] > 0 for k in kirilim}
        L += ["", ("**Tüm alt dönemlerde aynı işaret → dönem artefaktı değil, "
                   "yapısal.**" if len(isaretler) == 1 else
                   "**İşaret dönemler arası değişiyor → rejime bağlı, dikkatli "
                   "yorumla.**"), ""]

    L += ["## Faz artefaktı denetimi", "",
          "Tek fazlı ölçüm (mevcut `chart.measure_edge` yöntemi) ile tüm-faz "
          "ortalaması arasındaki fark:", "",
          "| Ufuk | Tek faz (faz 0) | Tüm faz ort. | Yayılım |",
          "|---|---:|---:|---:|"]
    for ad, s in engel["ufuklar"].items():
        if not s.get("yeterli"):
            continue
        L.append(f"| {ad} | {s['faz_0_ortalama']:+.2f}% | {s['ortalama']:+.2f}% | "
                 f"{s['yayilim']:.2f}p |")
    L += ["", "_Yayılım, `config.yaml chart.dogrulama.min_anlamli_fark_puan` "
          "değerinden büyükse o ufukta tek-fazlı 'zayıf kanıt' bulguları faz "
          "artefaktından ayırt edilemez._", "",
          "---", "_Genel bilgilendirme amaçlıdır; yatırım tavsiyesi değildir._"]
    return "\n".join(L)


ENGEL_CACHE = "data/gram_engeli.json"


def engel_ozet(cfg: dict, engel: dict) -> dict:
    """Karar motorunun okuyacağı sadeleştirilmiş ölçüm (JSON'a yazılır).

    Neden önbellek: engel ölçümü 2561 gün × tüm fazlar üzerinde koşuyor; günlük
    raporun her çalışmasında tekrarlanacak bir iş değil. Ölçüm ancak yeni veri
    anlamlı biriktiğinde değişir (`python -m src.gram engel` ile tazelenir).
    """
    rt = roundtrip_cost_pct(cfg, cfg["karar"]["enstruman"])
    return {
        "olcum_utc": util.utcnow().isoformat(),
        "veri_ilk": engel["ilk"], "veri_son": engel["son"], "n_gun": engel["n_gun"],
        "enstruman": cfg["karar"]["enstruman"], "roundtrip_pct": rt,
        "ufuklar": {
            ad: {
                "gun": s["gun"], "n_bagimsiz": s["n_bagimsiz"],
                "taban_ortalama_pct": s["ortalama"],
                "kazanma_pct": s["kazanma_pct"],
                "maliyet_sonrasi_kazanma_pct": s.get("maliyet_sonrasi_kazanma_pct"),
                "en_kotu_pct": s["en_kotu"],
                "taktik_esik_puan": esik_pct(s["ortalama"], rt, "taktik"),
                "cekirdek_esik_puan": esik_pct(s["ortalama"], rt, "cekirdek"),
            }
            for ad, s in engel["ufuklar"].items() if s.get("yeterli")
        },
    }


def engel_oku(cfg: dict) -> Optional[dict]:
    """Önbelleklenmiş ölçüm; yoksa None (rapor bloğu sessizce düşer)."""
    return util.read_json(util.abspath(ENGEL_CACHE), None)


def run_engel(cfg: dict) -> str:
    """Ölçümü koşar, `reports/gram_engeli.md` + `data/gram_engeli.json` yazar."""
    from . import db, logging_setup
    logging_setup.setup("gram", cfg)
    con = db.connect(cfg)
    try:
        engel = sat_engeli(cfg, con)
        kirilim = alt_donem_kirilimi(
            cfg, con, cfg["karar"]["ufuklar_gun"]["1ay"],
            [("2016-19", "2016-01-01", "2019-12-31"),
             ("2020-22", "2020-01-01", "2022-12-31"),
             ("2023-26", "2023-01-01", "2026-12-31")])
    finally:
        con.close()
    md = format_engel_md(cfg, engel, kirilim)
    path = util.abspath(f"{cfg['paths']['reports_dir']}/gram_engeli.md")
    path.write_text(md, encoding="utf-8")
    util.write_json(util.abspath(ENGEL_CACHE), engel_ozet(cfg, engel))
    log.info("gram engeli yazildi: %s (+ %s)", path, ENGEL_CACHE)
    return str(path)


if __name__ == "__main__":
    import sys

    util.load_env()
    _cfg = util.load_config()
    if len(sys.argv) > 1 and sys.argv[1] == "engel":
        print(run_engel(_cfg))
    else:
        for _e in ("banka_hesap", "altins1", "fiziki_gram"):
            print(f"{_e:14s} gidiş-dönüş: %{roundtrip_cost_pct(_cfg, _e):.2f}")
