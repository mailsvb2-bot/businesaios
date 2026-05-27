from __future__ import annotations

from runtime._internal.effects_clients import telegram_client as tg_mod
from runtime._internal.effects_clients.telegram_client import TelegramClient
from runtime.platform.delivery_state import RECOVERY_PHASE, DeliveryState


class _Queue:
    def __init__(self) -> None:
        self.items = []

    def enqueue(self, **kwargs):
        self.items.append(dict(kwargs))
        return True


class _DummyTransport:
    pass


def test_telegram_client_requeues_stale_accepted_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token')
    monkeypatch.setattr(
        tg_mod,
        'http_json',
        lambda method, url, payload, timeout_s, transport=None: {'ok': True, 'result': {'message_id': 777}},
    )
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    queue = _Queue()
    client = TelegramClient(outbound_queue=queue, transport=_DummyTransport(), delivery_state=state)

    state.mark_accepted(
        'recovery-key',
        payload_digest='digest-1',
        metadata={
            'method': 'sendMessage',
            'chat_id': '42',
            'payload': {'chat_id': '42', 'text': 'hello', 'parse_mode': 'HTML', 'disable_web_page_preview': True},
            'timeout_s': 0,
            'priority': 'normal',
            'critical': True,
            'mode': 'queued',
        },
    )

    receipt = state.get_receipt('recovery-key')
    assert receipt is not None
    original_get = state.get_receipt

    def _patched_get(key: str):
        out = original_get(key)
        if key == 'recovery-key' and out is not None:
            out['accepted_at_ms'] = 1
        return out

    monkeypatch.setattr(state, 'get_receipt', _patched_get)
    monkeypatch.setattr(tg_mod, '_delivery_key', lambda **kwargs: 'recovery-key')
    monkeypatch.setattr(tg_mod, '_payload_digest', lambda payload: 'digest-1')

    ok, meta = client.send_message(chat_id='42', text='hello')

    assert ok is True
    assert meta['mode'] == 'queued_recovery'
    assert meta['delivery_phase'] == RECOVERY_PHASE
    assert len(queue.items) == 1

    updated = state.get_receipt('recovery-key')
    assert updated is not None
    assert updated['metadata']['recovery'] is True
    assert updated['metadata']['recovery_attempts'] == 1
    assert updated['metadata']['payload'] == {'chat_id': '42', 'text': 'hello', 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    assert updated['metadata']['timeout_s'] == 30
    assert updated['metadata']['priority'] == 'normal'
    assert updated['metadata']['critical'] is True

    queue.items[0]['fn']()
    finalized = state.get_receipt('recovery-key')
    assert finalized is not None
    assert finalized['delivery_phase'] == 'finalized'
    assert finalized['external_id'] == '777'


def test_telegram_client_bulk_marks_stale_inflight_receipts_for_recovery(tmp_path) -> None:
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    client = TelegramClient(outbound_queue=_Queue(), transport=_DummyTransport(), delivery_state=state)
    state.mark_accepted('msg-a', payload_digest='a', metadata={'timeout_s': 1, 'payload': {'x': 1}})
    state.mark_accepted('msg-b', payload_digest='b', metadata={'timeout_s': 1, 'payload': {'x': 2}})

    recovered = client.recover_inflight_accepted_receipts(stale_after_ms=0, limit=10)

    assert [item['message_id'] for item in recovered] == ['msg-a', 'msg-b']
    assert all(item['delivery_phase'] == RECOVERY_PHASE for item in recovered)
    assert all(item['metadata']['recovery_attempts'] == 1 for item in recovered)
