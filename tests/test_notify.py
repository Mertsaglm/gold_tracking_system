"""Bildirim motoru saf çekirdek testleri: eşik değerlendirme + soğuma/tavan."""
from src import notify, util

CFG = util.load_config()


def _ctx(**kw):
    base = {"all_fresh": True, "prim": 0.0, "prim_z": None, "spread": None,
            "spread_p90": None, "daily_move": None, "atr": None, "quarter_z": None}
    base.update(kw)
    return base


def test_prim_threshold_fires():
    al = notify.evaluate_thresholds(_ctx(prim=2.0), CFG)
    assert any(a["tip"] == "prim_sapma" for a in al)


def test_prim_within_band_no_fire():
    al = notify.evaluate_thresholds(_ctx(prim=0.5), CFG)
    assert not any(a["tip"] == "prim_sapma" for a in al)


def test_zscore_threshold():
    al = notify.evaluate_thresholds(_ctx(prim_z=2.5), CFG)
    assert any(a["tip"] == "prim_z" for a in al)


def test_spread_p90():
    al = notify.evaluate_thresholds(_ctx(spread=0.5, spread_p90=0.3), CFG)
    assert any(a["tip"] == "makas" for a in al)


def test_daily_move_atr():
    al = notify.evaluate_thresholds(_ctx(daily_move=100, atr=40), CFG)  # 100 > 2*40
    assert any(a["tip"] == "gunluk_hareket" for a in al)


def test_weekend_suppresses_anomaly():
    # üç bacak FRESH değil -> anomali bildirimi yok
    al = notify.evaluate_thresholds(_ctx(all_fresh=False, prim=5.0, prim_z=9.0), CFG)
    assert al == []


def test_each_alert_has_triple():
    al = notify.evaluate_thresholds(_ctx(prim=2.0), CFG)[0]
    assert al["kural"] and al["gerekce"] and al["gecersizlik"]


# ---------- soğuma / tavan ----------
def test_cooldown_blocks_repeat():
    alerts = [{"tip": "prim_sapma", "kural": "k", "deger": 2, "gerekce": "g", "gecersizlik": "x"}]
    # 1 saat önce gönderilmiş, soğuma 24s -> engellenir
    state = {"last_sent": {"prim_sapma": "2026-07-07T10:00:00+00:00"}, "daily": {}}
    to_send, _ = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 6)
    assert to_send == []


def test_cooldown_allows_after_window():
    alerts = [{"tip": "prim_sapma", "kural": "k", "deger": 2, "gerekce": "g", "gecersizlik": "x"}]
    state = {"last_sent": {"prim_sapma": "2026-07-06T10:00:00+00:00"}, "daily": {}}
    # 25 saat sonra -> geçer
    to_send, ns = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 6)
    assert len(to_send) == 1
    assert ns["last_sent"]["prim_sapma"] == "2026-07-07T11:00:00+00:00"


def test_daily_cap():
    alerts = [{"tip": f"t{i}", "kural": "k", "deger": 1, "gerekce": "g", "gecersizlik": "x"}
              for i in range(10)]
    state = {"last_sent": {}, "daily": {}}
    to_send, ns = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 3)
    assert len(to_send) == 3            # tavan
    assert ns["daily"]["2026-07-07"] == 3


# ---------- ATR / günlük hareket referansı: BUGÜN dışlanmalı ----------
def _db_ile_history(tmp_path, satirlar):
    import copy

    from src import db
    c = copy.deepcopy(CFG)
    c["paths"]["db"] = str(tmp_path / "t.sqlite")
    c["paths"]["db_dump"] = str(tmp_path / "t.sql")
    con = db.connect(c)
    for d, fiyat in satirlar:
        con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                    "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, 4000.0, 47.0, fiyat, "test"))
    con.commit()
    return c, con


def test_atr_bugunun_yarim_barini_saymaz(tmp_path):
    """`update_recent` hafta içi bugünün YARIM barını da yazıyor; ATR onu saymamalı.

    Yarım bar hem ATR'yi bozar hem gün içinde her koşumda değiştirir → eşik
    kayan hedefe döner.
    """
    from datetime import date, timedelta
    bugun = util.local_today()
    b = date.fromisoformat(bugun)
    # 20 kapanmış gün: her gün +10₺ → ATR ≈ 10
    satirlar = [((b - timedelta(days=20 - i)).isoformat(), 6000.0 + 10 * i)
                for i in range(20)]
    c, con = _db_ile_history(tmp_path, satirlar)
    atr_temiz = notify._atr_from_history(con)
    # şimdi bugünün YARIM barı gelsin — uçuk bir sıçramayla
    con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                (bugun, 4000.0, 47.0, 9999.0, "yarim"))
    con.commit()
    assert notify._atr_from_history(con) == atr_temiz, "yarım bar ATR'ye sızdı"
    con.close()


def test_gunluk_hareket_bugunun_kendi_kapanisiyla_karsilastirmaz(tmp_path):
    """Rapor koştuktan sonra alarm fiyatı KENDİSİYLE karşılaştırıp ~0 buluyordu."""
    from datetime import date, timedelta
    bugun = util.local_today()
    b = date.fromisoformat(bugun)
    satirlar = [((b - timedelta(days=20 - i)).isoformat(), 6000.0 + 10 * i)
                for i in range(20)]
    c, con = _db_ile_history(tmp_path, satirlar)
    dun_kapanis = satirlar[-1][1]
    # bugünün yarım barı, güncel fiyata ÇOK yakın yazılıyor (gerçek durum)
    guncel = 6300.0
    con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                (bugun, 4000.0, 47.0, guncel, "yarim"))
    con.commit()
    row = con.execute("SELECT gram_teorik FROM history_daily WHERE date < ? "
                      "ORDER BY date DESC LIMIT 1", (bugun,)).fetchone()
    con.close()
    assert row["gram_teorik"] == dun_kapanis
    assert abs(guncel - row["gram_teorik"]) > 100, "referans dünkü kapanış olmalı"
