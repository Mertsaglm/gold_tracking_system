"""Bölüm 2 — AI sentez paketi (v3'ün sıfır maliyetli kısmı).

Güncel yapılandırılmış veri paketi (PROJE-REHBERI 6.4) + başına yapıştırılabilir hazır
prompt. Kullanıcı çıktıyı kopyalayıp istediği güçlü AI'a yapıştırır → senaryo/sentez
yorumunu oradan alır (API maliyeti sıfır). Model çağrısı YAPILMAZ; sadece paket üretilir.
"""
from __future__ import annotations

import json
import logging

from . import calc, db, util

log = logging.getLogger("aipaket")

PROMPT_BASI = """\
Sen bir FİNANSAL VERİ YORUMLAYICISISIN. Aşağıda Türkiye altın piyasasının güncel, \
yapılandırılmış verisi var. Görevin: SENARYO ANALİZİ ve GENEL YATIRIM BİLGİLENDİRMESİ üretmek.

KURALLAR (SPK uyumu):
- Kişiye özel yatırım tavsiyesi VERME. "Sen şunu al/sat" deme; "tarihsel olarak / senaryo / \
eğilim" dilini kullan. Herkes için aynı genel bilgilendirme.
- "Kesin", "garanti", "kesinlikle yükselir/düşer" YASAK. Belirsizliği açıkça belirt.
- Fiyatı SEN üretme; yalnızca aşağıdaki VERİ PAKETİ'ni kullan (modellerin bilgisi eskidir).
- VERİ KALİTESİ alanına bak: "veri_bekliyor"/"veri yok" olanlara güvenme, eksik olduğunu söyle.
- BACKTEST notlarını dikkate al: bu projede rejim/sinyal "üstünlükleri" taban çizgisine karşı \
büyük ölçüde ANLAMSIZ çıktı (TL enflasyonu artefaktı). Abartma.

ÇIKTI ŞEMASI (her sinyal için):
{ "sinyal": "...", "yon": "...", "gerekce": ["..."], "guven": "düşük|orta|yüksek",
  "gecersizlik": "bu senaryo şu olursa bozulur: ...", "ufuk": "...",
  "uyari": "Genel bilgilendirme; yatırım tavsiyesi değildir." }

Önce 2-3 senaryo (iyimser/baz/kötümser), sonra bu şemayla 2-4 sinyal üret.

===== VERİ PAKETİ (JSON) =====
"""


def build_package(cfg: dict) -> dict:
    con = db.connect(cfg)
    latest = db.latest_prim(con)
    off = cfg.get("timezone_offset_hours", 3)
    tarih = util.to_local(util.utcnow(), off).isoformat()

    pkt = {"tarih": tarih, "kaynak": "altin-takip-mvp"}

    if latest:
        pkt["fiyat"] = {
            "ons_usd": latest["ons_usd"], "usdtry": latest["usdtry"],
            "gram_teorik": latest["theoretical"], "gram_piyasa_has": latest["market_has"],
            "prim_pct": latest["prim_pct"], "spread_pct": latest["spread_pct"],
            "ceyrek_prim_pct": latest["quarter_prim_pct"],
        }

    # z-skor durumu
    zmin = cfg["stats"]["zscore_min_samples"]
    n_days = db.count_valid_prim_days(con)
    if n_days >= zmin:
        series = db.prim_series(con, only_valid=True)
        z = calc.zscore(series[:-1], series[-1], zmin)
        pkt["prim_zskoru"] = {"deger": z.value, "n": z.n, "gun": n_days}
    else:
        pkt["prim_zskoru"] = {"durum": "veri_bekliyor",
                              "mevcut_gun": n_days, "gereken_gun": zmin}

    # EVDS makro
    try:
        from .evds_job import context
        pkt["makro"] = context(cfg)
    except Exception as e:
        log.warning("makro hata: %s", e)

    # kadran paneli
    try:
        from . import indicators
        panel = indicators.build_panel(cfg, pkt.get("makro", {}).get("reel_net_mevduat"))
        pkt["kadran"] = {
            "gostergeler": [{"ad": s.name, "etiket": s.label, "detay": s.detail}
                            for s in panel["signals"]],
            "uzlasi": panel["consensus"],
        }
    except Exception as e:
        log.warning("kadran hata: %s", e)

    # rejim + backtest köprüsü
    try:
        from .signals import _current_regime
        regime, rstat = _current_regime(cfg, con)
        bridge = None
        if rstat and rstat.get("n"):
            bridge = (f"{rstat['n']} örtüşmeyen dönem; 3 ay medyan {rstat['medyan']:+.1f}%, "
                      f"kazanma %{rstat['kazanma_pct']:.0f}"
                      + (" (zayıf N)" if rstat.get("weak") else ""))
        pkt["rejim"] = {"guncel": regime, "backtest_kopru": bridge,
                        "not": "Backtest'te rejim üstünlükleri tabana karşı zayıf/anlamsız."}
    except Exception as e:
        log.warning("rejim hata: %s", e)

    # veri kalitesi
    pkt["veri_kalitesi"] = _veri_kalitesi(cfg, con, latest, n_days, zmin)
    con.close()
    return pkt


def _veri_kalitesi(cfg, con, latest, n_days, zmin) -> dict:
    hist = con.execute("SELECT COUNT(*) FROM history_daily").fetchone()[0]
    evds = con.execute("SELECT COUNT(*) FROM evds_daily").fetchone()[0]
    return {
        "canli_prim_kaydi": db.latest_prim(con) is not None,
        "bacak_durumu": latest["reason"] if latest else "veri yok",
        "indicative": bool(latest["indicative"]) if latest else None,
        "zskor_arsivi": f"{n_days}/{zmin} gün ({'hazır' if n_days >= zmin else 'birikiyor'})",
        "history_daily_gun": hist,
        "evds_satir": evds,
        "uyari": "Eksik/indicative alanlara güvenme; canlı arşiv Actions ile dolar.",
    }


def build_prompt(cfg: dict) -> str:
    pkt = build_package(cfg)
    return (PROMPT_BASI
            + json.dumps(pkt, ensure_ascii=False, indent=2)
            + "\n===== VERİ PAKETİ SONU =====\n")


def main(cfg: dict) -> str:
    from . import logging_setup
    logging_setup.setup("aipaket", cfg)
    text = build_prompt(cfg)
    print(text)
    return text


if __name__ == "__main__":
    util.load_env()
    main(util.load_config())
