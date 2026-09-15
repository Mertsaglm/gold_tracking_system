"""Eski üretim arşivini salt okunur açar; V1 kayıtlarını V2'ye dönüştürmez."""
from __future__ import annotations

import copy
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pandas as pd


@contextmanager
def connection(root, market, database=None):
    if database:
        con = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()
        return
    # GitHub'da SQL güncel, yerel binary aylarca eski kalabilir. Daima dump.
    from src import dbdump, util
    cfg = copy.deepcopy(util.load_config())
    dump = root / "data" / ("bist.sql" if market == "bist" else "altin.sql")
    if not dump.is_file():
        raise FileNotFoundError(f"Üretim arşivi bulunamadı: {dump.name}")
    with tempfile.TemporaryDirectory(prefix="advisor-history-") as tmp:
        cfg["paths"]["db"] = str(Path(tmp) / "history.db")
        cfg["paths"]["db_dump"] = str(dump)
        dbdump.restore(cfg)
        with connection(root, market, cfg["paths"]["db"]) as con:
            yield con


def load(con, market, asof):
    if market == "bist":
        frame = pd.read_sql_query(
            "SELECT b.ticker symbol,b.date,b.c close,b.c_tr total_close,b.h high,b.l low,"
            "b.v volume,u.sector,u.in_live FROM bars_daily b JOIN universe u USING(ticker) "
            "WHERE b.date<=? ORDER BY b.ticker,b.date", con, params=(asof,))
    else:
        frame = pd.read_sql_query(
            "SELECT date,gram_teorik close,gram_teorik total_close FROM history_daily "
            "WHERE date<=? ORDER BY date", con, params=(asof,))
        frame["symbol"] = "GRAM"
        frame["sector"] = "altin"
        frame["in_live"] = 1
        frame["high"] = frame["close"]
        frame["low"] = frame["close"]
        frame["volume"] = 1
    if frame.empty:
        raise ValueError("Analiz edilebilecek tarihsel fiyat bulunamadı.")
    frame = frame.drop_duplicates(["symbol", "date"]).sort_values(["symbol", "date"])
    return frame


def legacy_summary(con, market):
    if market == "bist":
        sources = [dict(r) for r in con.execute(
            "SELECT r.tool source,count(*) decisions,sum(p.action='plan_sec') selected,"
            "sum(o.ret_pct is not null) entered,avg(o.ret_pct) average_trade_return_pct,"
            "avg(o.alpha_vs_ew) average_excess_pct FROM predictions p "
            "JOIN llm_runs r USING(run_id) LEFT JOIN outcomes o USING(prediction_id) GROUP BY r.tool")]
        recent = [dict(r) for r in con.execute(
            "SELECT p.asof,p.ticker symbol,p.signal,p.action,p.thesis,p.key_risk,p.veto_code,"
            "p.entry_low,p.entry_high,p.stop_price,p.t1_price,p.news_refs "
            "FROM predictions p JOIN llm_runs r USING(run_id) "
            "WHERE p.asof=(SELECT max(asof) FROM predictions) AND r.tool != 'replay' ORDER BY p.ticker")]
        outcomes = [dict(r) for r in con.execute(
            "SELECT p.ticker symbol,p.asof,o.resolution,o.ret_pct,o.alpha_vs_ew,r.tool source "
            "FROM outcomes o JOIN predictions p USING(prediction_id) JOIN llm_runs r USING(run_id) "
            "ORDER BY o.resolved_date DESC")]
        duplicates = [dict(r) for r in con.execute(
            "SELECT asof,count(distinct run_id) runs FROM predictions GROUP BY asof HAVING runs>1")]
        return {"sources": sources, "recent": recent, "outcomes": outcomes,
                "duplicate_sessions": duplicates,
                "note": "V1 tahmin karnesi. Yüzdeler işlem ortalamasıdır; portföy getirisi değildir. Replay canlıya katılmaz."}
    sources = [dict(r) for r in con.execute(
        "SELECT p.kol source,p.hukum decision,count(*) decisions,sum(o.prediction_id is not null) resolved,"
        "avg(o.gram_etkisi_pct) gram_effect_pct FROM predictions p LEFT JOIN prediction_outcomes o "
        "ON p.id=o.prediction_id GROUP BY p.kol,p.hukum")]
    return {"sources": sources, "recent": [], "outcomes": [], "duplicate_sessions": [],
            "note": ("V1'de SAT kararı üretilmedi. " if not any(r["decision"] == "SAT" for r in sources) else "") + "Sayılar farklı ufuklardaki tahmin kayıtlarını içerir; bağımsız gün sayısı değildir. TUT isabeti gram artışını kanıtlamaz."}
