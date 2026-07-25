"""Eşik mantığı TEK KAYNAK: signals.evaluate_alerts → notify.evaluate_thresholds.

Gerçek olay: iki ayrı kopya sessizce ayrışmıştı — üretim (notify) 5 kural
uygularken CLI (signals) yalnız 3'ünü biliyordu (`makas` ve `ceyrek_prim`
eksikti). Bu testler ayrışmanın tekrar oluşmasını engeller.
"""
from src import notify, signals, util

CFG = util.load_config()


def _ctx(**kw):
    base = {"all_fresh": True, "prim": 0.0, "prim_z": None, "spread": None,
            "spread_p90": None, "daily_move": None, "atr": None, "quarter_z": None}
    base.update(kw)
    return base


def test_cli_uretimle_ayni_kural_kumesini_gorur(monkeypatch):
    """Her kuralı ateşleyen bir bağlam ver → CLI tam aynı tipleri döndürmeli."""
    hepsi = _ctx(prim=2.0, prim_z=2.5, spread=0.5, spread_p90=0.3,
                 daily_move=100, atr=40, quarter_z=2.5)
    monkeypatch.setattr(notify, "build_context", lambda _cfg: hepsi)

    beklenen = {a["tip"] for a in notify.evaluate_thresholds(hepsi, CFG)}
    gelen = {a["tip"] for a in signals.evaluate_alerts(CFG)}
    assert gelen == beklenen
    # ayrışmada kaybolan iki kural açıkça test ediliyor
    assert {"makas", "ceyrek_prim"} <= gelen


def test_cli_ciktisi_beklenen_alanlari_tasir(monkeypatch):
    monkeypatch.setattr(notify, "build_context", lambda _cfg: _ctx(prim=2.0))
    out = signals.evaluate_alerts(CFG)
    assert out and set(out[0]) == {"tip", "deger", "mesaj"}
    assert out[0]["tip"] == "prim_sapma"


def test_tetik_yokken_bos_liste(monkeypatch):
    monkeypatch.setattr(notify, "build_context", lambda _cfg: _ctx())
    assert signals.evaluate_alerts(CFG) == []


def test_hafta_sonu_bastirmasi_cli_icin_de_gecerli(monkeypatch):
    """all_fresh=False iken anomali bastırılır — kural tek yerde olduğu için otomatik."""
    monkeypatch.setattr(notify, "build_context",
                        lambda _cfg: _ctx(all_fresh=False, prim=5.0, prim_z=9.0))
    assert signals.evaluate_alerts(CFG) == []
