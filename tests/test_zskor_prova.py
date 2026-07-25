"""Z-skor kuru provası: kapı açılmadan dağılımı ölçer, bildirim GÖNDERMEZ.

Neden: 60 günlük kapı ~2026 Eylül'de açılacak ve `z > 2` bildirimi o ana dek hiç
ateşlenmemiş olacak. Prova, kapı açılmadan tetiklenme sıklığını görünür kılar.
"""
from src import db, signals, util


def _cfg(tmp_path):
    cfg = util.load_config()
    cfg["paths"]["db"] = str(tmp_path / "t.sqlite")
    return cfg


def _ekle(con, tarih, degerler, indicative=0, weekend=0):
    """Bir güne birden çok prim kaydı yazar (gün içi tekrar örneklemeyi taklit eder)."""
    for i, v in enumerate(degerler):
        con.execute(
            "INSERT INTO prim_history(ts_utc, prim_pct, indicative, weekend) "
            "VALUES(?,?,?,?)", (f"{tarih}T{9+i:02d}:00:00+00:00", v, indicative, weekend))


def test_gunluk_ortalama_gun_basina_tek_deger_verir(tmp_path):
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    _ekle(con, "2026-07-01", [1.0, 2.0, 3.0])      # ortalama 2.0
    _ekle(con, "2026-07-02", [4.0, 6.0])           # ortalama 5.0
    con.commit()
    gunluk = db.prim_daily_means(con)
    con.close()
    assert gunluk == [("2026-07-01", 2.0), ("2026-07-02", 5.0)]


def test_gunluk_ortalama_indicative_ve_haftasonu_haric(tmp_path):
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    _ekle(con, "2026-07-01", [1.0])
    _ekle(con, "2026-07-04", [99.0], weekend=1)     # hafta sonu → sayılmaz
    _ekle(con, "2026-07-05", [88.0], indicative=1)  # bayat → sayılmaz
    con.commit()
    gunluk = db.prim_daily_means(con)
    con.close()
    assert gunluk == [("2026-07-01", 1.0)]


def test_prova_kapi_kapaliyken_de_olcer(tmp_path):
    """Kritik: kapı kapalı (gün < 60) olsa bile z hesaplanmalı — provanın amacı bu."""
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    for i in range(1, 11):                          # 10 gün → kapı KAPALI
        _ekle(con, f"2026-07-{i:02d}", [1.0 + i * 0.1, 1.2 + i * 0.1])
    con.commit()
    r = signals.zscore_dry_run(cfg, con)
    con.close()
    assert r["kapi_acik"] is False                  # kapı hâlâ kapalı
    assert r["z_kayit_tabani"] is not None          # ama ölçüm YAPILDI
    assert r["z_gun_tabani"] is not None
    assert r["n_gun"] == 10


def test_prova_iki_tabani_ayri_raporlar(tmp_path):
    """Gün içi tekrar örnekleme std'yi şişirir → iki taban farklı z verir."""
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    for i in range(1, 13):
        # gün ortalaması sabit artıyor ama gün içi genis salinim var
        taban = 1.0 + i * 0.05
        _ekle(con, f"2026-07-{i:02d}", [taban - 0.5, taban, taban + 0.5])
    con.commit()
    r = signals.zscore_dry_run(cfg, con)
    con.close()
    # gün tabanında std daha küçük olmalı (gün içi gürültü ortalanır)
    assert r["std_gun"] < r["std_kayit"]
    assert r["z_kayit_tabani"] != r["z_gun_tabani"]


def test_prova_ceyregi_de_olcer(tmp_path):
    """Çeyrek z de aynı kapıya tabi ve o da hiç ateşlenmemiş → aynı prova ona da lazım."""
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    for i in range(1, 11):
        for saat in (9, 14):
            con.execute(
                "INSERT INTO prim_history(ts_utc, prim_pct, quarter_prim_pct, "
                "indicative, weekend) VALUES(?,?,?,0,0)",
                (f"2026-07-{i:02d}T{saat:02d}:00:00+00:00", -0.5 - i * 0.01, -1.0 + i * 0.03))
    con.commit()
    r = signals.zscore_dry_run(cfg, con)
    con.close()
    assert r["ceyrek_z_kayit"] is not None
    assert r["ceyrek_z_gun"] is not None
    assert r["ceyrek_tetiklenir_gun"] in (True, False)   # ölçülebilir durumda


def test_prova_yetersiz_veride_cokmez(tmp_path):
    cfg = _cfg(tmp_path)
    con = db.connect(cfg)
    _ekle(con, "2026-07-01", [1.0])
    con.commit()
    r = signals.zscore_dry_run(cfg, con)
    con.close()
    assert r["z_kayit_tabani"] is None              # None döner, patlamaz
    assert r["tetiklenir_kayit"] is False
