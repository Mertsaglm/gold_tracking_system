import json
from datetime import datetime
from pathlib import Path
import shutil

import pytest

from advisor import calendar, notifications
from advisor.accounts import state_path
from advisor.ledger import Ledger
from advisor.service import configuration
from scripts import gold_closing


@pytest.fixture
def archived_day(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'advisor').mkdir()
    shutil.copyfile(root / 'advisor/config.json', tmp_path / 'advisor/config.json')
    shutil.copyfile(root / 'holidays_tr.yaml', tmp_path / 'holidays_tr.yaml')
    state = state_path(tmp_path, configuration(tmp_path))
    ledger = Ledger(state / 'events.jsonl')
    ledger.add('session_check', 'friday', '2026-11-20T18:26:00+03:00',
               in_execution_window=True, expected_quotes=1, valid_quotes=1, decisions=1)
    ledger.save()
    sent = []

    class Response:
        status_code = 200

        def json(self):
            return {'ok': True, 'result': {'message_id': 412}}

    def post(*args, **kwargs):
        sent.append(kwargs['json']['text'])
        return Response()

    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test')
    monkeypatch.setattr(notifications.requests, 'post', post)
    return tmp_path, state, ledger, sent


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=calendar.IST)


def test_delayed_friday_close_warns_once_without_new_quote_or_valuation(archived_day):
    root, state, before, sent = archived_day
    snapshot = {'market': 'gold', 'generated_at': '2026-11-20T18:26:00+03:00',
                'monitoring': {'phase': 'protection'}, 'health': {'ledger_hash': before.root_hash}}
    (state / 'latest.json').write_text(json.dumps(snapshot))
    assert gold_closing.run(root, at('2026-11-20T23:17'), primary=True)['run_cycle']
    first = gold_closing.run(root, at('2026-11-21T00:07'), primary=False)
    assert first == {'run_cycle': False, 'sent': True, 'report_day': '2026-11-20'}
    assert not gold_closing.run(root, at('2026-11-21T00:18'), primary=True)['sent']
    assert not gold_closing.run(root, at('2026-11-22T00:07'), primary=False)['sent']
    assert not gold_closing.run(root, at('2026-11-23T10:15'), primary=True)['run_cycle']
    assert len(sent) == 1
    assert 'GÜN SONU · 2026-11-20' in sent[0]
    assert '1/1 çalışan işlem çevrimi' in sent[0]
    assert 'Kapanış fiyatı: doğrulanamadı.' in sent[0]
    after = Ledger(state / 'events.jsonl')
    assert after.events[:-1] == before.events
    assert after.events[-1]['kind'] == 'notification'
    assert after.events[-1]['data']['closing_complete'] is False
    assert after.events[-1]['data']['message_id'] == 412
    assert json.loads((state / 'latest.json').read_text()) == snapshot


def test_existing_archived_close_can_be_delivered_after_midnight(archived_day):
    root, state, ledger, sent = archived_day
    snapshot = {'market': 'gold', 'generated_at': '2026-11-20T23:17:00+03:00',
                'analysis_date': '2026-11-19', 'monitoring': {'phase': 'valuation'},
                'health': {'expected_quotes': 1, 'quote_coverage': 1,
                           'expected_analysis_date': '2026-11-19', 'ledger_hash': ledger.root_hash},
                'strategy': {'equity_try': 60000, 'valuation_complete': True}, 'decisions': []}
    (state / 'latest.json').write_text(json.dumps(snapshot))
    assert gold_closing.run(root, at('2026-11-21T00:07'), primary=False)['sent']
    assert 'kapanış verisi veya çevrimde eksik' not in sent[0]
    receipt = Ledger(state / 'events.jsonl').events[-1]['data']
    assert receipt['closing_complete'] is True
    assert receipt['snapshot_ledger_hash'] == ledger.root_hash
