from __future__ import annotations

from runtime._internal.effects_clients.telegram_client import TelegramClient
from runtime.messaging.outbound_message import OutboundMessage
from runtime.platform.delivery_state import DeliveryState


class _Queue:
    def __init__(self) -> None:
        self.items = []

    def enqueue(self, **kwargs):
        self.items.append(dict(kwargs))
        return None


class _DummyTransport:
    pass


def test_telegram_client_marks_queue_acceptance_and_dedups(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token')
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    queue = _Queue()
    client = TelegramClient(outbound_queue=queue, transport=_DummyTransport(), delivery_state=state)

    ok1, meta1 = client.send_message(chat_id='42', text='hello')
    assert ok1 is True
    assert meta1['delivery_phase'] == 'accepted_for_delivery'
    receipt = state.get_receipt(meta1['delivery_key'])
    assert receipt is not None
    assert receipt['delivery_phase'] == 'accepted_for_delivery'
    assert state.is_delivered(meta1['delivery_key']) is False

    ok2, meta2 = client.send_message(chat_id='42', text='hello')
    assert ok2 is True
    assert meta2['mode'] == 'dedup'
    assert meta2['delivery_phase'] == 'accepted_for_delivery'
    assert meta2['delivery_finalized'] is False
    assert len(queue.items) == 1


def test_telegram_delivery_dedup_from_accepted_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token')
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    msg = OutboundMessage(decision_id='d1', correlation_id='c1', tenant_id='t1', user_id='42', channel='telegram', text='hello')
    state.mark_accepted(msg.delivery_key, payload_digest=msg.payload_digest, metadata={'mode': 'queued'})

    class _Owner:
        delivery_state = state
        event_log = None
        telegram_outbound_queue = object()
        _last_sent = {}

        def _telegram_send_message(self, **kwargs):
            raise AssertionError('transport should not be called when accepted receipt already exists')

    from runtime._internal.effects_actions.telegram.messaging_parts.transport import telegram_delivery

    ok, meta = telegram_delivery(_Owner(), msg=msg)
    assert ok is True
    assert meta['dedup'] is True
    assert meta['delivery_phase'] == 'accepted_for_delivery'
    assert meta['delivery_finalized'] is False
