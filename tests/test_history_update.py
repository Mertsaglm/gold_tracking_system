"""history_daily artımlı güncelleme: 2026-07-07'den donuk kalan tabloyu
her gün tazeler (ATR + günlük hareket alarmlarının kaynağı, bkz DECISIONS #004).

Ağ gerektirmez — yfinance/EVDS çağrıları monkeypatch'lenir.
"""
from src import db, history, util


def _cfg(tmp_path):
    cfg = util.load_config()
    cfg["paths"]["db"] = str(tmp_path / "t.sqlite")
    return cfg


def test_update_recent_upserts_and_is_idempotent(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    con.execute(
        "INSERT OR REPLACE INTO evds_daily(date,series_code,value) VALUES(?,?,?)",
        ("2026-07-20", cfg["sources"]["evds"]["series"]["usdtry_sell"], 47.30),
    )
    con.commit()
    con.close()

    monkeypatch.setattr(history, "_yf_ons_daily",
                        lambda _cfg, _start, _min_days: ({"2026-07-20": 4070.0}, "GC=F"))
    res = history.update_recent(cfg, days=45)
    assert res["rows"] == 1

    con = db.connect(cfg)
    row = con.execute(
        "SELECT gram_teorik FROM history_daily WHERE date='2026-07-20'"
    ).fetchone()
    con.close()
    expected = 4070.0 / 31.1034768 * 47.30
    assert abs(row["gram_teorik"] - expected) < 0.01

    # tekrar çağırınca aynı gün üzerine yazar, ikinci satır YARATMAZ (idempotent)
    history.update_recent(cfg, days=45)
    con = db.connect(cfg)
    n = con.execute("SELECT COUNT(*) c FROM history_daily WHERE date='2026-07-20'").fetchone()["c"]
    con.close()
    assert n == 1


def test_update_recent_no_crash_when_sources_empty(tmp_path, monkeypatch):
    """EVDS/yfinance boş dönerse çökme yok (mevcut build_history_daily davranışı)."""
    cfg = _cfg(tmp_path)
    db.connect(cfg).close()
    monkeypatch.setattr(history, "_yf_ons_daily", lambda _cfg, _start, _min_days: ({}, None))
    res = history.update_recent(cfg, days=45)
    assert res == {"rows": 0}


def test_update_recent_passes_small_min_days(tmp_path, monkeypatch):
    """Kısa pencerede 200 gün asla dolmaz — update_recent küçük bir taban geçirmeli."""
    cfg = _cfg(tmp_path)
    db.connect(cfg).close()
    seen = {}

    def fake(_cfg, _start, min_days):
        seen["min_days"] = min_days
        return {}, None

    monkeypatch.setattr(history, "_yf_ons_daily", fake)
    history.update_recent(cfg, days=45)
    assert seen["min_days"] < 200


def test_build_history_daily_default_min_days_unchanged(tmp_path, monkeypatch):
    """Geriye dönük uyumluluk: eski çağıran (varsayılan) hâlâ 200 eşiği kullanır."""
    cfg = _cfg(tmp_path)
    db.connect(cfg).close()
    seen = {}

    def fake(_cfg, _start, min_days):
        seen["min_days"] = min_days
        return {}, None

    monkeypatch.setattr(history, "_yf_ons_daily", fake)
    history.build_history_daily(cfg)
    assert seen["min_days"] == 200


def test_history_daily_bugunun_yarim_barini_yazmaz(tmp_path, monkeypatch):
    """KAYNAK KAPATMA: bu tabloyu 16 yerden okuyoruz; tek tek korumak L-008'dir.

    En kritik tüketici `tahmin._fiyat_serisi`: `cozumle`'nin 3 günlük ÇIKIŞ
    ortalaması bugünün yarım barını içerebiliyordu ve o sonuç
    `prediction_outcomes`'a DEĞİŞTİRİLEMEZ yazılıyor.
    """
    import copy

    from src import db, history, util
    cfg = copy.deepcopy(util.load_config())
    cfg["paths"]["db"] = str(tmp_path / "t.sqlite")
    cfg["paths"]["db_dump"] = str(tmp_path / "t.sql")
    bugun = util.local_today()
    dun = "2026-07-24"

    con = db.connect(cfg)
    usd_kod = cfg["sources"]["evds"]["series"]["usdtry_sell"]
    for d in (dun, bugun):
        con.execute("INSERT OR REPLACE INTO evds_daily(date,series_code,value) "
                    "VALUES(?,?,?)", (d, usd_kod, 47.0))
    con.commit()
    con.close()

    # yfinance de bugünü döndürüyor (üretimde ölçülen davranış)
    monkeypatch.setattr(history, "_yf_ons_daily",
                        lambda c, s, min_days=200: ({dun: 4000.0, bugun: 4010.0}, "test"))
    history.build_history_daily(cfg, start="2026-07-01", min_days=1)

    con = db.connect(cfg)
    tarihler = [r[0] for r in con.execute(
        "SELECT date FROM history_daily ORDER BY date").fetchall()]
    con.close()
    assert dun in tarihler, "kapanmış gün yazılmalı"
    assert bugun not in tarihler, "bugünün yarım barı history_daily'ye yazıldı"
