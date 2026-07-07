"""Bot komut yetkilendirmesi (chat_id beyaz liste) testleri."""
import os

from src import telegram_bot as tb


def test_owner_allowed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    allowed = tb.allowed_chats({"telegram": {"extra_allowed_chat_ids": []}})
    assert tb.is_allowed("12345", allowed)


def test_unknown_blocked(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    allowed = tb.allowed_chats({"telegram": {"extra_allowed_chat_ids": []}})
    assert not tb.is_allowed("99999", allowed)


def test_extra_allowed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    allowed = tb.allowed_chats({"telegram": {"extra_allowed_chat_ids": [777, "888"]}})
    assert tb.is_allowed("777", allowed)      # int config -> str karşılaştırma
    assert tb.is_allowed("888", allowed)
    assert not tb.is_allowed("111", allowed)


def test_int_vs_str_chat_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    allowed = tb.allowed_chats({"telegram": {}})
    assert tb.is_allowed(12345, allowed)      # int gelen chat_id de eşleşir
