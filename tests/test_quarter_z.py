"""Çeyrek primi z-skoru: eşik + kural vardı ama build_context hep None döndürüyordu
→ "var sanılan" alarm hiç ateşlenemiyordu (LESSONS L-002: sessiz bozulma).

Artık prim z ile AYNI kapıya tabi; kapı açılınca kendiliğinden hesaplanır.
"""
from src import db, notify, util


def _cfg(tmp_path, zmin):
    cfg = util.load_config()
    cfg["paths"]["db"] = str(tmp_path / "q.sqlite")
    cfg["stats"]["zscore_min_samples"] = zmin
    return cfg


def _doldur(con, gun_sayisi):
    """gun_sayisi kadar geçerli gün, her gün 2 kayıt (prim + çeyrek primi)."""
    for i in range(1, gun_sayisi + 1):
        for saat in (9, 14):
            con.execute(
                "INSERT INTO prim_history(ts_utc, ons_usd, usdtry, theoretical, "
                "market_has, prim_pct, quarter_prim_pct, indicative, weekend) "
                "VALUES(?,?,?,?,?,?,?,0,0)",
                (f"2026-06-{i:02d}T{saat:02d}:00:00+00:00", 4000.0, 47.0, 6000.0,
                 5950.0, -0.5 - i * 0.01, -1.0 + i * 0.02))
    con.commit()


def test_kapi_kapaliyken_quarter_z_yok(tmp_path):
    cfg = _cfg(tmp_path, zmin=60)          # 10 gün < 60 → kapı kapalı
    con = db.connect(cfg)
    _doldur(con, 10)
    con.close()
    ctx = notify.build_context(cfg)
    assert ctx["quarter_z"] is None
    assert ctx["quarter"] is not None      # değerin kendisi yine de taşınır


def test_kapi_acilinca_quarter_z_hesaplanir(tmp_path):
    cfg = _cfg(tmp_path, zmin=5)           # 10 gün >= 5 → kapı açık
    con = db.connect(cfg)
    _doldur(con, 10)
    con.close()
    ctx = notify.build_context(cfg)
    assert ctx["quarter_z"] is not None    # ARTIK ölü değil
    assert isinstance(ctx["quarter_z"], float)


def test_quarter_z_prim_z_ile_ayni_kapiyi_kullanir(tmp_path):
    """Tutarlılık: ikisi de aynı gün eşiğine tabi olmalı."""
    cfg = _cfg(tmp_path, zmin=5)
    con = db.connect(cfg)
    _doldur(con, 10)
    con.close()
    ctx = notify.build_context(cfg)
    assert (ctx["prim_z"] is None) == (ctx["quarter_z"] is None)


def test_ceyrek_kurali_esik_asilinca_atesler():
    """Kural zaten vardı; ctx artık gerçek değer taşıdığı için ateşlenebiliyor."""
    cfg = util.load_config()
    ctx = {"all_fresh": True, "prim": 0.0, "prim_z": None, "spread": None,
           "spread_p90": None, "daily_move": None, "atr": None, "quarter_z": 2.5}
    al = notify.evaluate_thresholds(ctx, cfg)
    assert any(a["tip"] == "ceyrek_prim" for a in al)
