"""Giden mesaj arşivi (outbox): gönderilen mesajlar JSONL'a yazılır.

Ağ gerektirmez — yalnız _outbox_append test edilir (send_message'ın yan etkisi).
"""
import json

from src import telegram_bot as tb, util


def test_outbox_writes_record(tmp_path):
    cfg = util.load_config()
    cfg["telegram"]["outbox_enabled"] = True
    cfg["telegram"]["outbox_file"] = str(tmp_path / "outbox.jsonl")
    tb._outbox_append(cfg, "123456789", "merhaba dünya", None, 1)
    lines = (tmp_path / "outbox.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["text"] == "merhaba dünya"
    assert rec["chat"] == "789"                 # yalnız son 3 hane (gizlilik)
    assert rec["mode"] == "plain" and rec["parts"] == 1


def test_outbox_appends_multiple(tmp_path):
    cfg = util.load_config()
    cfg["telegram"]["outbox_enabled"] = True
    cfg["telegram"]["outbox_file"] = str(tmp_path / "o.jsonl")
    tb._outbox_append(cfg, "999", "a", None, 1)
    tb._outbox_append(cfg, "999", "b", "HTML", 2)
    lines = (tmp_path / "o.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["mode"] == "HTML"


def test_outbox_disabled_writes_nothing(tmp_path):
    cfg = util.load_config()
    cfg["telegram"]["outbox_enabled"] = False
    cfg["telegram"]["outbox_file"] = str(tmp_path / "none.jsonl")
    tb._outbox_append(cfg, "1", "x", None, 1)
    assert not (tmp_path / "none.jsonl").exists()
