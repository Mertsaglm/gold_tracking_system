"""Grafik yorumu saf fonksiyon testleri (Bölüm 6).

Proje konvansiyonu: yalnız saf fonksiyonlar test edilir, ağ çekicileri edilmez
(mock yok). Eşikler literal argüman olarak geçilir, cfg'den okunmaz.
"""
import math

from src import chart
from src.indicators import NOTR, OLUMLU, OLUMSUZ, YOK


# ---------------- find_pivots ----------------
def _dates(n):
    return ["2026-01-%02d" % (i + 1) for i in range(n)]


def test_find_pivots_zigzag():
    # tepe idx=2, dip idx=4 olacak sekilde zigzag
    highs = [10, 11, 15, 11, 10, 11, 12]
    lows = [9, 10, 14, 10, 5, 10, 11]
    p = chart.find_pivots(highs, lows, _dates(7), k=2)
    tepe = [x for x in p if x.kind == "tepe"]
    dip = [x for x in p if x.kind == "dip"]
    assert [t.idx for t in tepe] == [2]
    assert [d.idx for d in dip] == [4]


def test_find_pivots_confirm_idx_is_lookahead_guard():
    highs = [10, 11, 15, 11, 10]
    lows = [9, 10, 14, 10, 9]
    p = chart.find_pivots(highs, lows, _dates(5), k=2)
    assert p and all(x.confirm_idx == x.idx + 2 for x in p)


def test_find_pivots_flat_series_has_none():
    # duz plato k adet sahte pivot uretmemeli (strict komsu sarti)
    highs = [10] * 9
    lows = [9] * 9
    assert chart.find_pivots(highs, lows, _dates(9), k=2) == []


def test_find_pivots_too_short():
    assert chart.find_pivots([1, 2], [1, 2], _dates(2), k=5) == []


# ---------------- cluster_pivots ----------------
def _piv(price, kind="tepe", idx=0, date="2026-01-01"):
    return chart.Pivot(idx, date, price, kind, idx + 10)


def test_cluster_pivots_groups_near_prices():
    cl = chart.cluster_pivots([_piv(100), _piv(100.3), _piv(105)], tol_pct=0.5)
    assert len(cl) == 2
    assert len(cl[0]) == 2 and len(cl[1]) == 1


def test_cluster_pivots_is_scale_free():
    # ayni GORELI dizilim 10x olcekte de ayni kumelenmeli (yuzde tolerans)
    a = chart.cluster_pivots([_piv(100), _piv(100.3), _piv(105)], tol_pct=0.5)
    b = chart.cluster_pivots([_piv(1000), _piv(1003), _piv(1050)], tol_pct=0.5)
    assert [len(x) for x in a] == [len(x) for x in b]


def test_cluster_pivots_empty():
    assert chart.cluster_pivots([], tol_pct=0.5) == []


# ---------------- build_levels / score_level ----------------
def test_build_levels_uses_median_not_mean():
    # [100, 100, 130] -> medyan 100 (ortalama 110 olurdu)
    cl = [[_piv(100), _piv(100), _piv(130)]]
    lv = chart.build_levels(cl, "2026-01-01", half_life_days=180,
                            min_touches=3, karma_carpani=1.25)
    assert len(lv) == 1
    assert lv[0].price == 100
    assert lv[0].lo == 100 and lv[0].hi == 130


def test_build_levels_min_touches_filter():
    cl = [[_piv(100), _piv(100)]]
    assert chart.build_levels(cl, "2026-01-01", 180, 3, 1.25) == []
    assert len(chart.build_levels(cl, "2026-01-01", 180, 2, 1.25)) == 1


def test_build_levels_karma_when_both_kinds():
    cl = [[_piv(100, "tepe"), _piv(100, "dip"), _piv(100, "tepe")]]
    lv = chart.build_levels(cl, "2026-01-01", 180, 3, 1.25)
    assert lv[0].kind == "karma"


def test_score_recency_beats_stale():
    taze = chart.score_level(3, age_days=30, half_life_days=180,
                             is_karma=False, karma_carpani=1.25)
    eski = chart.score_level(3, age_days=900, half_life_days=180,
                             is_karma=False, karma_carpani=1.25)
    assert taze > eski
    assert eski < taze * 0.2          # 900g ~ 0.5**5 ~ %3


def test_score_karma_bonus():
    a = chart.score_level(3, 0, 180, False, 1.25)
    b = chart.score_level(3, 0, 180, True, 1.25)
    assert math.isclose(b, a * 1.25)


def test_score_zero_touches():
    assert chart.score_level(0, 0, 180, False, 1.25) == 0.0


# ---------------- nearest_levels ----------------
def test_nearest_levels_splits_and_orders():
    L = chart.Level
    lv = [L(90, 89, 91, "destek", 3, "a", "b", 1.0),
          L(95, 94, 96, "destek", 3, "a", "b", 1.0),
          L(110, 109, 111, "direnç", 3, "a", "b", 1.0)]
    out = chart.nearest_levels(lv, price=100, n=2)
    assert [x.price for x in out["destekler"]] == [95, 90]     # yakindan uzaga
    assert [x.price for x in out["direncler"]] == [110]


# ---------------- extremes ----------------
def test_extremes_windows_and_distance():
    highs = [10, 20, 15]
    lows = [5, 12, 11]
    out = chart.extremes(highs, lows, _dates(3), {"tum": 0})
    assert out["tum"]["zirve"][1] == 20
    assert out["tum"]["dip"][1] == 5
    # spot = son high = 15 -> zirveden %25 asagi
    assert math.isclose(out["tum"]["zirveden_uzaklik_pct"], (15 / 20 - 1) * 100)


# ---------------- true_range / atr ----------------
def test_true_range_gap_dominates():
    # onceki kapanis 100, bugun 105-104 -> gap |105-100|=5 > 1
    assert chart.true_range(105, 104, 100) == 5
    assert chart.true_range(105, 104, None) == 1


def test_atr_leading_none_then_value():
    h = [10, 11, 12, 13]
    l = [9, 10, 11, 12]
    c = [9.5, 10.5, 11.5, 12.5]
    a = chart.atr(h, l, c, window=2)
    assert a[0] is None
    assert a[1] is not None and a[-1] is not None


def test_atr_insufficient_data():
    assert chart.atr([1], [1], [1], window=5) == [None]


# ---------------- rsi ----------------
def test_rsi_monotonic_rise_is_100():
    vals = chart.rsi(list(range(1, 20)), window=14)
    assert math.isclose(vals[-1], 100.0)


def test_rsi_monotonic_fall_is_0():
    vals = chart.rsi(list(range(20, 1, -1)), window=14)
    assert math.isclose(vals[-1], 0.0)


def test_rsi_constant_series_no_zero_division():
    vals = chart.rsi([5.0] * 20, window=14)
    assert vals[-1] == 50.0           # sabit seri -> notr, patlamaz


# ---------------- bollinger ----------------
def test_bollinger_constant_series_pctb_none_not_inf():
    out = chart.bollinger([5.0] * 25, window=20, k=2.0)
    mid, up, dn, pctb = out[-1]
    assert mid == 5.0 and up == 5.0 and dn == 5.0
    assert pctb is None               # inf DEGIL


def test_bollinger_mid_is_mean():
    closes = list(range(1, 26))
    mid, up, dn, pctb = chart.bollinger(closes, window=5, k=2.0)[-1]
    assert math.isclose(mid, sum(closes[-5:]) / 5)


# ---------------- swing_structure ----------------
def test_swing_structure_uptrend_flags():
    piv = [_piv(10, "tepe"), _piv(12, "tepe"), _piv(5, "dip"), _piv(7, "dip")]
    s = chart.swing_structure(piv, n=2)
    assert s["hh"] and s["hl"]
    assert not s["lh"] and not s["ll"]


# ---------------- etiketleyiciler ----------------
def test_label_rsi_three_way():
    assert chart.label_rsi(75, 70, 30) == OLUMSUZ
    assert chart.label_rsi(25, 70, 30) == OLUMLU
    assert chart.label_rsi(50, 70, 30) == NOTR
    assert chart.label_rsi(None, 70, 30) == YOK


def test_label_rsi_boundaries_are_strict():
    # tam esikte NOTR (kesin buyuk/kucuk siniri)
    assert chart.label_rsi(70, 70, 30) == NOTR
    assert chart.label_rsi(30, 70, 30) == NOTR


def test_label_trend_structure():
    assert chart.label_trend_structure(True, True, False, False) == OLUMLU
    assert chart.label_trend_structure(False, False, True, True) == OLUMSUZ
    assert chart.label_trend_structure(True, False, False, True) == NOTR


def test_label_bollinger():
    assert chart.label_bollinger(1.2, 1.0, 0.0) == OLUMSUZ
    assert chart.label_bollinger(-0.1, 1.0, 0.0) == OLUMLU
    assert chart.label_bollinger(0.5, 1.0, 0.0) == NOTR
    assert chart.label_bollinger(None, 1.0, 0.0) == YOK


def test_label_level_proximity():
    assert chart.label_level_proximity(0.5, 1.0, "destek") == OLUMLU
    assert chart.label_level_proximity(0.5, 1.0, "direnç") == OLUMSUZ
    assert chart.label_level_proximity(3.0, 1.0, "destek") == NOTR
    assert chart.label_level_proximity(None, 1.0, "destek") == YOK


def test_label_vol_regime_is_not_directional():
    # yonsuz: olumlu/olumsuz DONDURMEZ, uzlasi oyuna girmez
    assert chart.label_vol_regime(0.2, 33.0, 66.0) == "düşük"
    assert chart.label_vol_regime(80.0, 33.0, 66.0) == "yüksek"
    assert chart.label_vol_regime(50.0, 33.0, 66.0) == "orta"
    for v in ("düşük", "yüksek", "orta"):
        assert v not in (OLUMLU, OLUMSUZ)


# ---------------- edge_verdict ----------------
def test_edge_verdict_no_measurement():
    assert chart.edge_verdict(None, 0, 15, 1.0) == "ölçüm yok"


def test_edge_verdict_weak_n_overrides_big_diff():
    # BU DOSYADAKI EN ONEMLI ASSERT: zayif N buyuk farki EZER
    v = chart.edge_verdict(+5.0, 3, 15, 1.0)
    assert "yetersiz" in v
    assert "kanıt" not in v


def test_edge_verdict_no_edge():
    assert chart.edge_verdict(+0.2, 40, 15, 1.0) == "kenar yok"


def test_edge_verdict_weak_evidence_only():
    v = chart.edge_verdict(+3.0, 40, 15, 1.0)
    assert v.startswith("zayıf kanıt")      # asla daha guclu bir dil yok


# ---------------- confirm_level ----------------
def test_confirm_level_counts_items():
    lv = chart.Level(90, 89, 91, "karma", 4, "2026-01-01", "2026-06-01", 2.0)
    out = chart.confirm_level(lv, price=100, atr_val=1.0, structure_label=OLUMLU,
                              momentum_label=OLUMLU, present_in_1y=True,
                              present_in_2y=True, min_touches=3)
    assert out["yon"] == "destek"
    assert out["toplam"] == 5
    assert out["teyit_sayisi"] == 5          # hepsi saglaniyor
    assert len(out["maddeler"]) == 5


def test_confirm_level_direnc_yonu():
    lv = chart.Level(110, 109, 111, "direnç", 2, "2026-01-01", "2026-06-01", 1.0)
    out = chart.confirm_level(lv, price=100, atr_val=1.0, structure_label=OLUMLU,
                              momentum_label=OLUMLU, present_in_1y=False,
                              present_in_2y=True, min_touches=3)
    assert out["yon"] == "direnç"
    # trend OLUMLU ama yon direnc -> trend uyumlu DEGIL
    assert out["teyit_sayisi"] < out["toplam"]


def test_bonferroni_note_mentions_count():
    assert "36" in chart.bonferroni_note(36)


# ---------------- format_chart_md / Telegram guvenligi ----------------
def _fake_result():
    L = chart.Level(3900, 3880, 3920, "destek", 3, "2026-01-01", "2026-06-01", 1.4)
    return {
        "sembol": "GC=F", "son_bar": "2026-07-20", "spot": 4010.0,
        "atr": 78.0, "atr_pct": 1.95, "vol_rejim": "yüksek", "bar_sayisi": 2649,
        "seviyeler": {"destekler": [L], "direncler": []},
        "teyitler": {3900: chart.confirm_level(L, 4010, 78.0, OLUMLU, NOTR,
                                               True, True, 2)},
        "ekstremler": {"tum": {"zirve": ("2026-01-29", 5586.0),
                               "dip": ("2016-01-04", 1063.0),
                               "zirveden_uzaklik_pct": -28.2,
                               "dipten_uzaklik_pct": 277.0}},
        "zirve_yakin": False, "rsi": 40.0, "pctb": 0.25,
        "yapi": {"son_tepeler": [4880.0], "son_dipler": [3962.0]},
        "etiketler": {"yapi": OLUMSUZ, "rsi": NOTR, "bollinger": NOTR},
        "sinyaller": [], "uzlasi": {"score": 0, "n": 3, "yon": NOTR, "normalized": 0.0},
        "usdtry": 47.14, "edge": {}, "troy": 31.1034768,
    }


def test_format_chart_md_has_no_pipe_tables():
    # Telegram parse_mode=None -> tablolar boru corbasina doner; MADDE kullanilmali
    out = chart.format_chart_md(_fake_result())
    assert "|" not in out


def test_format_chart_md_empty_is_silent():
    assert chart.format_chart_md({}) == ""
    assert chart.format_chart_md({"yok": "kapalı"}) == ""


def test_format_chart_md_keeps_numbers_after_telegram_strip():
    from src.telegram_bot import _md_to_plain
    plain = _md_to_plain(chart.format_chart_md(_fake_result()))
    assert plain.strip()
    assert "3,880" in plain and "4,010" in plain      # seviye + spot korunuyor


def test_format_chart_md_states_geometry_not_claim():
    # Projenin epistemik kurali: olculmemis seviye YON IDDIASI tasiyamaz
    out = chart.format_chart_md(_fake_result())
    assert "geometridir" in out
    assert "yön" in out and "iddiası için kullanılamaz" in out


def test_format_chart_md_ath_warning_when_at_peak():
    r = _fake_result()
    r["zirve_yakin"] = True
    r["seviyeler"]["direncler"] = []
    out = chart.format_chart_md(r)
    assert "DİRENÇ YOKTUR" in out      # zirvede ustte direnc UYDURULMAZ


# ---------------- ohlc_daily DB gidis-donusu ----------------
def test_ohlc_daily_roundtrip(tmp_path):
    from src import db, dbdump, ohlc_hist
    cfg = {"paths": {"db": str(tmp_path / "t.sqlite"), "db_dump": str(tmp_path / "t.sql")},
           "timezone_offset_hours": 3}
    con = db.connect(cfg)
    con.execute("INSERT INTO ohlc_daily(date,symbol,o,h,l,c,v,source) "
                "VALUES('2026-01-02','GC=F',1,2,0.5,1.5,10,'yfinance')")
    con.execute("INSERT INTO ohlc_daily(date,symbol,o,h,l,c,v,source) "
                "VALUES('2026-01-03','GC=F',1.5,3,1,2.5,11,'yfinance')")
    con.commit()
    rows = ohlc_hist.load_ohlc(con, "GC=F")
    assert [r["date"] for r in rows] == ["2026-01-02", "2026-01-03"]   # tarih sirali
    assert rows[1]["h"] == 3
    con.close()
    dbdump.dump(cfg)
    dbdump.restore(cfg)
    con2 = db.connect(cfg)
    assert len(ohlc_hist.load_ohlc(con2, "GC=F")) == 2     # dump/restore hayatta kaldi
    con2.close()


def test_drop_unclosed_bar():
    from src import ohlc_hist
    bars = [{"date": "2026-07-19"}, {"date": "2026-07-20"}, {"date": "2026-07-21"}]
    # daily.yml 15:35 UTC'de kosuyor, CME ~21:00'de kapaniyor -> bugunun bari YARIM
    out = ohlc_hist.drop_unclosed_bar(bars, "2026-07-21")
    assert [b["date"] for b in out] == ["2026-07-19", "2026-07-20"]
    assert ohlc_hist.drop_unclosed_bar([], "2026-07-21") == []
