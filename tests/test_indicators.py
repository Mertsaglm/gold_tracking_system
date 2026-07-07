"""Kadran paneli etiketleme mantığı testleri (saf fonksiyonlar)."""
from src import indicators as ind
from src.indicators import Signal, OLUMLU, NOTR, OLUMSUZ, YOK


def test_real_rate_falling_is_positive():
    assert ind.label_real_rate(-10.0, 5.0) == OLUMLU     # 10bps düşüş
    assert ind.label_real_rate(+10.0, 5.0) == OLUMSUZ    # 10bps artış
    assert ind.label_real_rate(+3.0, 5.0) == NOTR        # eşik altı


def test_dxy_falling_is_positive():
    assert ind.label_dxy(-1.0, 0.5) == OLUMLU
    assert ind.label_dxy(+1.0, 0.5) == OLUMSUZ
    assert ind.label_dxy(+0.2, 0.5) == NOTR


def test_gma_positions():
    assert ind.label_gma(price=110, gma50=105, gma200=100) == OLUMLU
    assert ind.label_gma(price=90, gma50=95, gma200=100) == OLUMSUZ
    assert ind.label_gma(price=102, gma50=98, gma200=100) == NOTR  # karışık


def test_gld_rising_is_positive():
    assert ind.label_gld(+1.0, 0.5) == OLUMLU
    assert ind.label_gld(-1.0, 0.5) == OLUMSUZ
    assert ind.label_gld(+0.1, 0.5) == NOTR


def test_real_deposit_thresholds():
    assert ind.label_real_deposit(1.0, 2.0, 8.0) == OLUMLU    # düşük reel -> altın olumlu
    assert ind.label_real_deposit(10.0, 2.0, 8.0) == OLUMSUZ  # yüksek reel -> olumsuz
    assert ind.label_real_deposit(5.0, 2.0, 8.0) == NOTR


def test_consensus_excludes_veri_yok():
    sigs = [
        Signal("a", OLUMLU, ""),
        Signal("b", OLUMSUZ, ""),
        Signal("c", YOK, ""),        # paydaya girmemeli
    ]
    c = ind.consensus(sigs)
    assert c["n"] == 2               # YOK sayılmadı
    assert c["score"] == 0


def test_consensus_direction():
    sigs = [Signal("a", OLUMLU, ""), Signal("b", OLUMLU, ""), Signal("c", NOTR, "")]
    c = ind.consensus(sigs)
    assert c["normalized"] > 0.25
    assert c["yon"] == OLUMLU


def test_consensus_all_veri_yok():
    c = ind.consensus([Signal("a", YOK, ""), Signal("b", YOK, "")])
    assert c["n"] == 0 and c["yon"] == NOTR


def test_signal_score_mapping():
    assert Signal("x", OLUMLU, "").score == 1
    assert Signal("x", OLUMSUZ, "").score == -1
    assert Signal("x", NOTR, "").score == 0
    assert Signal("x", YOK, "").score is None
