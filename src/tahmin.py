"""Bölüm 8c — Tahmin kaydı ve karne: sistemin dürüstlük altyapısı.

Bu modül olmadan "AL" demek kehanettir; bu modülle birlikte İDDİA olur.

Akış üç adımdır ve üçü de `daily_job`'dan günlük çağrılır:

    kaydet()          asof=T-1 için hüküm üret ve DEĞİŞTİRİLEMEZ şekilde yaz
    girisleri_doldur()  T+1'de: girişi (T'nin fiyatı) ayrı tabloya yaz
    cozumle()         vadesi gelen tahminleri gram uzayında çöz

NEDEN GİRİŞ AYRI TABLODA: hüküm asof=T-1'de verilir, ama uygulanacağı fiyat
T'nin kapanışıdır ve hüküm anında HENÜZ BİLİNMEZ. Aynı satıra yazmak, bilinmeyen
bir fiyatı biliyormuş gibi kaydetmek — yani look-ahead — olurdu.

ÇÖZÜM KURALI (kullanıcının "tam gün veremez" itirazının cevabı):
  - Giriş ve çıkış İKİSİ de 3 işlem günü ortalaması. Simetri şart: yalnız çıkışı
    ortalamak, pozitif sürüklenen bir seride sistematik TUT yanlılığı yaratır.
  - Doğruluk gram uzayında ölçülür (`gram.hukum_dogru_mu`), fiyat uzayında değil.
  - ATR ölü bandı YOK: ayarlanabilir eşik = karneyi güzelleştirmek için
    oynanabilir kol. Tek eşik (gidiş-dönüş maliyeti) piyasadan gelir.

KAÇINMA YASAK: her asof tarihi tam olarak bir hüküm üretmek zorundadır.
"Bu gün emin değilim" diye atlamak, karneyi seçerek temizlemenin kapısıdır;
emin olunmayan gün TUT olarak kaydedilir ve karnede o şekilde sayılır.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from . import gram, util

log = logging.getLogger("tahmin")

ORT_PENCERE = 3          # giriş/çıkış ortalaması alınan işlem günü sayısı


# ================= SAF ÇEKİRDEK (testli) =================

def pencere_ortalamasi(fiyatlar: list[float], merkez: int,
                       pencere: int = ORT_PENCERE) -> Optional[float]:
    """`merkez` indeksi etrafında `pencere` günlük ortalama (t-1, t, t+1).

    Tek gün gürültüsünü eler. Kullanıcı "tam gün veremez" dedi — bir hükmü tek
    bir kapanışın kaprisine bağlamak hem haksız hem gürültülü olurdu.
    Sınırda pencere kırpılır; en az 1 gözlem yeter.
    """
    if not fiyatlar or merkez < 0 or merkez >= len(fiyatlar):
        return None
    yari = pencere // 2
    dilim = [p for p in fiyatlar[max(0, merkez - yari):merkez + yari + 1] if p]
    return sum(dilim) / len(dilim) if dilim else None


def tahmini_hedef_tarih(asof: str, horizon_isgunu: int) -> str:
    """İşlem günü ufkunun TAKVİM tarihine yaklaşık karşılığı.

    Yalnız GÖSTERİM içindir ("~şu tarihte çözülecek"). Gerçek çözüm daima
    işlem günü indeksinden yapılır (`cozumle`), bu tahminden değil — aksi
    halde tatiller karneyi kaydırırdı. Haftada 5 işlem günü varsayımı.
    """
    from datetime import date, timedelta
    y, m, d = (int(x) for x in asof.split("-"))
    return (date(y, m, d) + timedelta(days=round(horizon_isgunu * 7 / 5))).isoformat()


def hedef_indeks(tarihler: list[str], asof: str, horizon: int) -> Optional[int]:
    """asof'tan `horizon` İŞLEM GÜNÜ sonrasının indeksi (takvim günü değil)."""
    import bisect
    i = bisect.bisect_left(tarihler, asof)
    if i >= len(tarihler) or tarihler[i] != asof:
        i -= 1                                  # asof işlem günü değilse bir öncesi
    if i < 0:
        return None
    j = i + horizon
    return j if j < len(tarihler) else None


def gram_etkisi(hukum: str, gram_carry_kazanc_pct: float,
                roundtrip_pct: float) -> float:
    """Bu hükme UYULSAYDI gram sayısı nasıl değişirdi (%)?

    ASIL METRİK budur — isabet oranı değil. Bir sistem %70 isabetle gram
    kaybedebilir (küçük kazançlar, büyük kayıplar); bu alan onu yakalar.

      SAT_xx → oran kadar pozisyon satılır: kazanç × oran − maliyet × oran
      TUT/AL → satılmadı: gram sayısı değişmez (0.0)
    """
    if not hukum.startswith("SAT"):
        return 0.0
    try:
        oran = int(hukum.split("_")[1]) / 100.0
    except (IndexError, ValueError):
        oran = 1.0
    return (gram_carry_kazanc_pct - roundtrip_pct) * oran


def karne_ozeti(satirlar: list[dict], zayif_n: int) -> dict:
    """Çözülmüş tahminlerden karne. Ham isabet oranı TEK BAŞINA raporlanmaz.

    Sebep: gram TL yukarı sürükleniyor, yani "hep TUT" diyen bir taş bile yüksek
    isabet alır. Anlamlı olan TABANA KARŞI FARK — `backtest.py`'nin
    "mutlak medyan TL enflasyonu artefaktıdır" uyarısının aynısı.
    """
    n = len(satirlar)
    if n == 0:
        return {"cozulmus": 0, "yeterli_mi": False}
    isabet = sum(1 for s in satirlar if s["hukum_dogru"]) / n * 100.0
    taban = sum(1 for s in satirlar if s["taban_dogru"]) / n * 100.0
    return {
        "cozulmus": n,
        "isabet_pct": isabet,
        "taban_pct": taban,
        "isabet_farki_puan": isabet - taban,
        # Toplam gram etkisi: bileşik değil toplamsal — pozisyonun tamamı her
        # seferinde işleme girmiyor, oranlı giriyor.
        "gram_etkisi_pct": sum(s["gram_etkisi_pct"] for s in satirlar),
        "hukum_dagilimi": {h: sum(1 for s in satirlar if s["hukum"] == h)
                           for h in sorted({s["hukum"] for s in satirlar})},
        "yeterli_mi": n >= zayif_n,
        "zayif_n": zayif_n,
    }


# ================= IO: kayıt / giriş / çözüm =================

def _fiyat_serisi(con) -> tuple[list[str], list[float]]:
    rows = con.execute("SELECT date, gram_teorik FROM history_daily "
                       "WHERE gram_teorik IS NOT NULL ORDER BY date").fetchall()
    return [r["date"] for r in rows], [r["gram_teorik"] for r in rows]


def _son_kapali_gun(con) -> Optional[str]:
    r = con.execute("SELECT MAX(date) d FROM history_daily "
                    "WHERE gram_teorik IS NOT NULL").fetchone()
    return r["d"] if r else None


def kaydet(cfg: dict, con, asof_date: Optional[str] = None,
           kaynak: str = "canli") -> list[int]:
    """asof için TÜM ufuk × kol kombinasyonlarında hüküm üretip yazar.

    Aynı (model, kaynak, asof, ufuk, kol) için ikinci kez çağrılmak zararsızdır:
    UNIQUE kısıtı sayesinde sessizce atlanır. Bu, `daily_job`'un aynı gün iki kez
    koşmasına dayanıklı olmasını sağlar.
    """
    from . import karar, ozellikler as oz
    k = cfg["karar"]
    asof = asof_date or _son_kapali_gun(con)
    if not asof:
        log.warning("history_daily bos — tahmin kaydedilemedi")
        return []

    tarihler, _ = _fiyat_serisi(con)
    engel = gram.engel_oku(cfg)
    # TEK GİRİŞ NOKTASI: canlı üretim ve tarihsel replay aynı fonksiyonu çağırır.
    # Buradan başka bir yolla veri okumak look-ahead garantisini düşürür
    # (bkz. ozellikler.py modül docstring'i).
    ozellikler = oz.feature_vector(cfg, con, asof)

    simdi = util.utcnow().isoformat()
    yazilan = []
    for ufuk_ad, h in k["ufuklar_gun"].items():
        j = hedef_indeks(tarihler, asof, h)
        # Yeni bir tahminde hedef HENÜZ TAKVİMDE YOKTUR (geleceği tahmin ediyoruz)
        # → gösterim için yaklaşık takvim tarihi yazılır; çözüm indeksten yapılır.
        hedef = tarihler[j] if j is not None else tahmini_hedef_tarih(asof, h)
        ufuk_engel = (engel or {}).get("ufuklar", {}).get(ufuk_ad)
        kapi = karar.kapi_durumu(cfg, karne(cfg, con) if kaynak == "canli" else None)
        kollar = {
            "cekirdek": karar.cekirdek_hukum(ozellikler.get("reel_net_mevduat"),
                                             k["cekirdek"]),
            "taktik": karar.taktik_hukum(ufuk_engel, kapi,
                                         k["taktik"]["maliyet_emniyet_carpani"]),
        }
        for kol, h_res in kollar.items():
            cur = con.execute(
                "INSERT OR IGNORE INTO predictions("
                " created_utc, model_version, kaynak, asof_date, horizon_days,"
                " target_date, kol, hukum, skor, guven,"
                " beklenen_gram_kazanc_pct, esik_pct, kapi_acik, ozellikler_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (simdi, k["model_version"], kaynak, asof, h, hedef, kol,
                 h_res["hukum"], h_res.get("skor"), None,
                 h_res.get("beklenen_gram_kazanc_pct"),
                 (ufuk_engel or {}).get("taktik_esik_puan" if kol == "taktik"
                                        else "cekirdek_esik_puan"),
                 1 if kapi["acik"] else 0,
                 # Özellik vektörünün TAMAMI saklanır: bir hükmü sonradan
                 # denetlemek ancak o an neyi gördüğünü bilerek mümkün.
                 json.dumps({**ozellikler, "gerekce": h_res["gerekce"]},
                            ensure_ascii=False)))
            if cur.rowcount:
                yazilan.append(cur.lastrowid)
    con.commit()
    if yazilan:
        log.info("tahmin kaydedildi: asof=%s adet=%d", asof, len(yazilan))
    return yazilan


def girisleri_doldur(cfg: dict, con) -> int:
    """Girişi henüz doldurulmamış tahminler için giriş fiyatını yazar.

    Giriş = asof'tan SONRAKİ işlem gününün 3 günlük ortalaması. O gün henüz
    kapanmadıysa (pencere tamamlanmadıysa) atlanır ve ertesi gün denenir —
    yarım pencereyle doldurmak çıkışla simetriyi bozardı.
    """
    tarihler, fiyatlar = _fiyat_serisi(con)
    if not tarihler:
        return 0
    idx = {d: i for i, d in enumerate(tarihler)}
    simdi = util.utcnow().isoformat()
    n = 0
    for r in con.execute(
            "SELECT p.id, p.asof_date FROM predictions p "
            "LEFT JOIN prediction_entries e ON e.prediction_id = p.id "
            "WHERE e.prediction_id IS NULL").fetchall():
        i = idx.get(r["asof_date"])
        if i is None or i + 1 >= len(tarihler):
            continue
        giris_i = i + 1
        if giris_i + ORT_PENCERE // 2 >= len(tarihler):
            continue                                  # pencere daha tamamlanmadı
        ort = pencere_ortalamasi(fiyatlar, giris_i)
        if ort is None:
            continue
        con.execute("INSERT OR IGNORE INTO prediction_entries("
                    " prediction_id, giris_date, giris_gram_teorik, doldurma_utc)"
                    " VALUES(?,?,?,?)",
                    (r["id"], tarihler[giris_i], ort, simdi))
        n += 1
    con.commit()
    if n:
        log.info("giris dolduruldu: %d tahmin", n)
    return n


def cozumle(cfg: dict, con, bugun: Optional[str] = None) -> int:
    """Vadesi dolmuş ve girişi dolu tahminleri gram uzayında çözer."""
    tarihler, fiyatlar = _fiyat_serisi(con)
    if not tarihler:
        return 0
    idx = {d: i for i, d in enumerate(tarihler)}
    bugun = bugun or tarihler[-1]
    stopaj = cfg["sources"]["evds"].get("mevduat_stopaj_pct", 15.0)
    rt = gram.roundtrip_cost_pct(cfg, cfg["karar"]["enstruman"])
    dep_kod = cfg["sources"]["evds"]["series"]["mevduat_3ay"]
    dep = {r["date"]: r["value"] for r in con.execute(
        "SELECT date, value FROM evds_daily WHERE series_code=? AND value IS NOT NULL",
        (dep_kod,)).fetchall()}
    dep_t = sorted(dep)
    simdi = util.utcnow().isoformat()

    n = 0
    for r in con.execute(
            "SELECT p.id, p.hukum, p.horizon_days, e.giris_date, e.giris_gram_teorik "
            "FROM predictions p "
            "JOIN prediction_entries e ON e.prediction_id = p.id "
            "LEFT JOIN prediction_outcomes o ON o.prediction_id = p.id "
            "WHERE o.prediction_id IS NULL").fetchall():
        gi = idx.get(r["giris_date"])
        if gi is None:
            continue
        ci = gi + r["horizon_days"]
        # Çıkış penceresinin TAMAMI kapanmış olmalı — yarım pencere asimetri yaratır
        if ci + ORT_PENCERE // 2 >= len(tarihler) or tarihler[ci] > bugun:
            continue
        cikis = pencere_ortalamasi(fiyatlar, ci)
        if cikis is None:
            continue
        faiz = gram.asof_faiz(dep_t, dep, r["giris_date"])
        kazanc = gram.gram_carry_gain_pct(
            r["giris_gram_teorik"], cikis, faiz, r["horizon_days"], stopaj)
        if kazanc is None:
            continue
        dogru = gram.hukum_dogru_mu(r["hukum"], kazanc, rt)
        taban_dogru = gram.hukum_dogru_mu("TUT", kazanc, rt)
        con.execute(
            "INSERT OR IGNORE INTO prediction_outcomes("
            " prediction_id, cozum_utc, cikis_date, cikis_gram_teorik,"
            " mevduat_yillik_pct, gram_carry_kazanc_pct, roundtrip_maliyet_pct,"
            " hukum_dogru, taban_dogru, gram_etkisi_pct) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (r["id"], simdi, tarihler[ci], cikis, faiz, kazanc, rt,
             1 if dogru else 0, 1 if taban_dogru else 0,
             gram_etkisi(r["hukum"], kazanc, rt)))
        n += 1
    con.commit()
    if n:
        log.info("tahmin cozuldu: %d", n)
    return n


def karne(cfg: dict, con, kol: str = "taktik", kaynak: str = "canli",
          model_version: Optional[str] = None) -> dict:
    """Çözülmüş tahminlerin karnesi. Varsayılan `taktik` — kapı bunu okur."""
    mv = model_version or cfg["karar"]["model_version"]
    rows = con.execute(
        "SELECT p.hukum, o.hukum_dogru, o.taban_dogru, o.gram_etkisi_pct "
        "FROM predictions p JOIN prediction_outcomes o ON o.prediction_id = p.id "
        "WHERE p.model_version=? AND p.kaynak=? AND p.kol=?",
        (mv, kaynak, kol)).fetchall()
    k = karne_ozeti([dict(r) for r in rows], cfg["karar"]["karne"]["zayif_n"])
    k["kol"], k["kaynak"], k["model_version"] = kol, kaynak, mv
    # Bekleyen: kaydedilmiş ama henüz çözülmemiş
    k["bekleyen"] = con.execute(
        "SELECT COUNT(*) c FROM predictions p "
        "LEFT JOIN prediction_outcomes o ON o.prediction_id = p.id "
        "WHERE o.prediction_id IS NULL AND p.model_version=? AND p.kaynak=? "
        "AND p.kol=?", (mv, kaynak, kol)).fetchone()["c"]
    r = con.execute(
        "SELECT MIN(target_date) d FROM predictions p "
        "LEFT JOIN prediction_outcomes o ON o.prediction_id = p.id "
        "WHERE o.prediction_id IS NULL AND p.model_version=? AND p.kaynak=? "
        "AND p.kol=?", (mv, kaynak, kol)).fetchone()
    k["ilk_cozum_tarihi"] = r["d"] if r else None
    return k


def format_karne_md(k: dict) -> str:
    if k["cozulmus"] == 0:
        ilk = f", ilki ~{k['ilk_cozum_tarihi']}" if k.get("ilk_cozum_tarihi") else ""
        return "\n".join([
            "## 📋 Tahmin Karnesi", "",
            f"**Henüz çözülmüş tahmin yok.** {k['bekleyen']} tahmin vadesini "
            f"bekliyor{ilk} _(kol `{k['kol']}`)_.", "",
            "_Karne dolana kadar hükümler ölçülen tarihsel tabana dayanır; "
            "canlı isabet iddiası YOKTUR._", ""])
    L = ["## 📋 Tahmin Karnesi", "",
         f"_kol `{k['kol']}` · model {k['model_version']} · kaynak {k['kaynak']}_", "",
         "| Metrik | Değer |", "|---|---:|",
         f"| Çözülmüş tahmin | {k['cozulmus']} |",
         f"| İsabet | %{k['isabet_pct']:.0f} |",
         f"| Taban (\"hep TUT\") | %{k['taban_pct']:.0f} |",
         f"| **Tabana fark** | **{k['isabet_farki_puan']:+.1f} puan** |",
         f"| **Gram etkisi** | **{k['gram_etkisi_pct']:+.2f}%** |",
         f"| Bekleyen | {k['bekleyen']} |", ""]
    if not k["yeterli_mi"]:
        L += [f"⚠️ **Ölçüm yetersiz** (N={k['cozulmus']} < {k['zayif_n']}). "
              "Bu karneden sonuç çıkarma.", ""]
    L += ["_Asıl metrik gram etkisidir: bir sistem yüksek isabetle gram "
          "kaybedebilir (küçük kazanç, büyük kayıp)._", ""]
    return "\n".join(L)


def main(cfg: dict) -> dict:
    from . import db, logging_setup
    logging_setup.setup("tahmin", cfg)
    con = db.connect(cfg)
    try:
        out = {"kaydedilen": len(kaydet(cfg, con)),
               "giris": girisleri_doldur(cfg, con),
               "cozulen": cozumle(cfg, con)}
        print(format_karne_md(karne(cfg, con)))
        return out
    finally:
        con.close()


if __name__ == "__main__":
    util.load_env()
    print(main(util.load_config()))
