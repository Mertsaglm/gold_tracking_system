"""archive_fetch retry: kaynak boş dönerse tekrar dener (veri kalitesi).

GitHub cron throttling'i çözmez; çalışan turda transient truncgil/yfinance
hatalarını kurtarır (arşivde ~%7 geçersiz kayıt bundandı).
"""
from src import archive_fetch as af, util
from src.sources.truncgil import TruncgilSnapshot
from src.sources.yf import YfSnapshot


def test_retry_recovers_after_transient_fail():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            return TruncgilSnapshot(ok=False, error="net")
        return TruncgilSnapshot(ok=True, prices={"gram_has_altin": (1.0, 2.0)})

    res = af._retry(flaky, lambda s: s.ok, retries=3, backoff=0)
    assert res.ok and calls["n"] == 3


def test_retry_zero_is_single_call():
    """Geriye dönük uyumluluk: retries=0 → tek deneme, eski davranış."""
    calls = {"n": 0}

    def once():
        calls["n"] += 1
        return TruncgilSnapshot(ok=False)

    af._retry(once, lambda s: s.ok, retries=0, backoff=0)
    assert calls["n"] == 1


def test_retry_gives_up_returns_last_no_crash():
    res = af._retry(lambda: YfSnapshot(ons_usd=None, usdtry=None),
                    lambda s: s.ons_usd is not None, retries=2, backoff=0)
    assert res.ons_usd is None            # en iyi çaba döner, çökmez


def test_fetch_row_wires_retry(monkeypatch):
    cfg = util.load_config()
    cfg["sources"]["fetch_retries"] = 2
    cfg["sources"]["fetch_retry_backoff_s"] = 0
    tcalls = {"n": 0}

    def tfetch(_cfg):
        tcalls["n"] += 1
        if tcalls["n"] < 2:
            return TruncgilSnapshot(ok=False)      # ilk deneme boş
        return TruncgilSnapshot(ok=True,
                                prices={"gram_has_altin": (6100.0, 6101.0)})

    monkeypatch.setattr(af.truncgil, "fetch", tfetch)
    monkeypatch.setattr(af.yf, "fetch",
                        lambda _c: YfSnapshot(ons_usd=4000.0, usdtry=47.0))
    row = af.fetch_row(cfg)
    assert tcalls["n"] == 2                          # retry devreye girdi
    assert row["gram_has_sell"] == 6101.0
    assert row["ons_usd"] == 4000.0
