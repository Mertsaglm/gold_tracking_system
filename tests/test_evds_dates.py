"""Bölüm 0 regresyon: EVDS tarih ISO dönüşümü ve sıralama."""
import sqlite3

from src.sources.evds import to_iso_date


# ---------- Saf dönüşüm ----------
def test_daily_ddmmyyyy():
    assert to_iso_date("07-07-2026") == "2026-07-07"
    assert to_iso_date("01-02-2016") == "2016-02-01"
    assert to_iso_date("31-12-2021") == "2021-12-31"


def test_monthly_yyyy_m():
    assert to_iso_date("2016-1") == "2016-01-01"
    assert to_iso_date("2015-12") == "2015-12-01"
    assert to_iso_date("2026-5") == "2026-05-01"


def test_already_iso():
    assert to_iso_date("2026-07-07") == "2026-07-07"


def test_quarterly():
    assert to_iso_date("2020-Q1") == "2020-01-01"
    assert to_iso_date("2020-Q3") == "2020-07-01"


def test_yearly():
    assert to_iso_date("2019") == "2019-01-01"


def test_none_empty():
    assert to_iso_date(None) is None
    assert to_iso_date("") is None
    assert to_iso_date("  ") is None


def test_ordering_is_chronological():
    """Kritik kusur regresyonu: eski formatta '01-01-2018' < '01-02-2016' idi.
    ISO'da ORDER BY date kronolojik olmalı."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE t(date TEXT, v REAL)")
    raw = ["01-02-2016", "01-01-2018", "31-12-2021", "07-07-2026", "2016-1", "2015-12"]
    for d in raw:
        con.execute("INSERT INTO t VALUES(?,1)", (to_iso_date(d),))
    asc = [r[0] for r in con.execute("SELECT date FROM t ORDER BY date ASC")]
    assert asc[0] == "2015-12-01"      # en eski
    assert asc[-1] == "2026-07-07"     # en yeni
    assert asc == sorted(asc)          # string sıralaması == kronolojik
    # BETWEEN doğru aralık
    n = con.execute(
        "SELECT COUNT(*) FROM t WHERE date BETWEEN '2016-01-01' AND '2018-12-31'"
    ).fetchone()[0]
    assert n == 3   # 2016-02-01, 2018-01-01, 2016-01-01
    con.close()
