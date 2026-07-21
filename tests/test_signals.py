"""Sinyal motoru saf fonksiyon testleri."""
from src import signals


def test_atr_proxy_constant_series_zero():
    # sabit fiyat -> ATR 0
    assert signals.atr_proxy([100.0] * 20) == 0.0


def test_atr_proxy_known():
    # her gün +10 -> |Δ|=10 -> ATR=10
    prices = [100 + 10 * i for i in range(20)]
    assert signals.atr_proxy(prices, window=14) == 10.0


def test_atr_proxy_insufficient():
    assert signals.atr_proxy([1, 2, 3], window=14) is None


def test_signal_schema_shape():
    s = signals._signal("test", "alim", ["birikimci"], ["gerekçe"], "orta",
                        "geçersizlik koşulu", "1 ay")
    for k in ("sinyal", "yon", "profil", "gerekce", "guven", "gecersizlik",
              "ufuk", "backtest", "uyari"):
        assert k in s
    assert s["backtest"] == "tarihsel doğrulaması yok"   # varsayılan
    assert "yatırım tavsiyesi değildir" in s["uyari"]


def test_format_signals_md_empty():
    out = signals.format_signals_md({"signals": []})
    assert "Sinyaller" in out


# --- z-skor kapısı: kayıt değil GÜN sayar ---------------------------------
def _prim_db(tmp_path, rows):
    """rows: (ts_utc, indicative, weekend) listesi."""
    from src import db
    cfg = {"paths": {"db": str(tmp_path / "t.sqlite"), "db_dump": str(tmp_path / "t.sql")}}
    con = db.connect(cfg)
    for ts, ind, wk in rows:
        con.execute("INSERT INTO prim_history(ts_utc,prim_pct,indicative,weekend) "
                    "VALUES(?,-0.5,?,?)", (ts, ind, wk))
    con.commit()
    return con


def test_valid_prim_days_counts_days_not_records(tmp_path):
    from src import db
    # 3 gün × 10 kayıt = 30 kayıt ama 3 gün
    rows = [(f"2026-07-{d:02d}T{h:02d}:00:00+00:00", 0, 0)
            for d in (7, 8, 9) for h in range(10)]
    con = _prim_db(tmp_path, rows)
    assert db.count_valid_prim(con) == 30
    assert db.count_valid_prim_days(con) == 3
    con.close()


def test_valid_prim_days_excludes_indicative_and_weekend(tmp_path):
    from src import db
    rows = [("2026-07-07T10:00:00+00:00", 0, 0),
            ("2026-07-08T10:00:00+00:00", 1, 0),   # indicative -> sayılmaz
            ("2026-07-11T10:00:00+00:00", 0, 1)]   # hafta sonu -> sayılmaz
    con = _prim_db(tmp_path, rows)
    assert db.count_valid_prim_days(con) == 1
    con.close()
