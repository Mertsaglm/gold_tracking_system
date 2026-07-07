"""SQL dump → restore round-trip ve determinizm testleri."""
from src import db, dbdump


def _cfg(tmp_path):
    return {
        "paths": {"db": str(tmp_path / "t.sqlite"), "db_dump": str(tmp_path / "t.sql")},
    }


def test_dump_restore_equal(tmp_path):
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    con.execute("INSERT INTO history_daily(date,ons_usd,usdtry,gram_teorik,ons_source)"
                " VALUES('2020-01-01',1500,6.0,289.3,'GC=F')")
    con.execute("INSERT INTO history_daily(date,ons_usd,usdtry,gram_teorik,ons_source)"
                " VALUES('2020-01-02',1510,6.1,296.1,'GC=F')")
    con.execute("INSERT INTO evds_daily(date,series_code,value) VALUES('2020-01-01','X',1.5)")
    con.execute("INSERT INTO prim_history(ts_utc,prim_pct) VALUES('2020-01-01T00:00+00:00',-0.5)")
    con.commit()
    before = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t, _, _ in dbdump._TABLES}
    con.close()

    dbdump.dump(cfg)
    r = dbdump.restore(cfg)
    assert r["restored"] is True
    assert r["counts"] == before                    # satır sayıları birebir


def test_dump_is_deterministic(tmp_path):
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    for d in ("2020-01-03", "2020-01-01", "2020-01-02"):   # sırasız ekle
        con.execute("INSERT INTO history_daily(date,ons_usd,usdtry,gram_teorik,ons_source)"
                    f" VALUES('{d}',1,1,1,'x')")
    con.commit()
    con.close()
    p1 = dbdump.dump(cfg, str(tmp_path / "a.sql"))
    p2 = dbdump.dump(cfg, str(tmp_path / "b.sql"))
    assert open(p1, encoding="utf-8").read() == open(p2, encoding="utf-8").read()
    # tarih sırası korunmalı (deterministik)
    content = open(p1, encoding="utf-8").read()
    i1 = content.index("2020-01-01")
    i2 = content.index("2020-01-02")
    i3 = content.index("2020-01-03")
    assert i1 < i2 < i3


def test_sql_escaping(tmp_path):
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    # tek tırnak içeren değer
    con.execute("INSERT INTO reports(date,path,created_utc) VALUES('2020-01-01',?,?)",
                ("O'Brien/path", "2020-01-01T00:00+00:00"))
    con.commit()
    con.close()
    dbdump.dump(cfg)
    r = dbdump.restore(cfg)
    assert r["counts"]["reports"] == 1
    con = db.connect(cfg)
    val = con.execute("SELECT path FROM reports").fetchone()[0]
    con.close()
    assert val == "O'Brien/path"                     # kaçış doğru
