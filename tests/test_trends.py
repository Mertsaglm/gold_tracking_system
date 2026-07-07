"""Google Trends kontrarian etiketleme testleri (saf)."""
from src import trends
from src.indicators import OLUMLU, NOTR, OLUMSUZ


def test_high_interest_is_contrarian_negative():
    assert trends.label_trends(2.5, 2.0) == OLUMSUZ    # kalabalık yoğun


def test_low_interest_is_positive():
    assert trends.label_trends(-2.5, 2.0) == OLUMLU     # düşük ilgi


def test_normal_interest_neutral():
    assert trends.label_trends(0.5, 2.0) == NOTR
    assert trends.label_trends(-1.0, 2.0) == NOTR


def test_threshold_boundary():
    assert trends.label_trends(2.0, 2.0) == NOTR        # eşit -> nötr (strict >)
    assert trends.label_trends(2.01, 2.0) == OLUMSUZ
