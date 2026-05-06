from __future__ import annotations

from runtime._internal.effects_clients import telegram_client as tg_mod
from runtime._internal.effects_clients.telegram_client import TelegramClient
from runtime.platform.delivery_state import DeliveryState


class _WorkerQueue:
    def __init__(self) -> None:
        self.items = []

    def enqueue(self, *, method, chat_id, fn, meta=None, critical=True, priority=50, kind='normal'):
        self.items.append(
            {
                'method': method,
                'chat_id': chat_id,
                'fn': fn,
                'meta': dict(meta or {}),
                'critical': critical,
                'priority': priority,
                'kind': kind,
            }
        )
        return True

    def drain(self):
        results = []
        while self.items:
            item = self.items.pop(0)
            results.append(item['fn']())
        return results


class _DummyTransport:
    pass


def test_send_message_queue_worker_finalizes_delivery(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token')
    monkeypatch.setattr(
        tg_mod,
        'http_json',
        lambda method, url, payload, timeout_s, transport=None: {'ok': True, 'result': {'message_id': 777}},
    )
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    queue = _WorkerQueue()
    client = TelegramClient(outbound_queue=queue, transport=_DummyTransport(), delivery_state=state)

    ok, meta = client.send_message(chat_id='42', text='hello')

    assert ok is True
    assert meta['mode'] == 'queued'
    assert meta['delivery_phase'] == 'accepted_for_delivery'
    assert meta['delivery_finalized'] is False
    assert state.is_delivered(meta['delivery_key']) is False
    assert len(queue.items) == 1

    queue.drain()

    receipt = state.get_receipt(meta['delivery_key'])
    assert receipt is not None
    assert receipt['delivery_phase'] == 'finalized'
    assert receipt['external_id'] == '777'
    assert receipt['metadata']['mode'] == 'queued_worker'
    assert state.is_delivered(meta['delivery_key']) is True


def test_send_audio_queue_worker_finalizes_delivery(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token')
    monkeypatch.setattr(
        tg_mod,
        'http_json',
        lambda method, url, payload, timeout_s, transport=None: {'ok': True, 'result': {'message_id': 888}},
    )
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    queue = _WorkerQueue()
    client = TelegramClient(outbound_queue=queue, transport=_DummyTransport(), delivery_state=state)

    ok, meta = client.send_audio(chat_id='42', audio_url='https://example.com/a.mp3')

    assert ok is True
    assert meta['mode'] == 'queued'
    assert meta['delivery_phase'] == 'accepted_for_delivery'
    assert meta['delivery_finalized'] is False
    assert state.is_delivered(meta['delivery_key']) is False
    assert len(queue.items) == 1

    queue.drain()

    receipt = state.get_receipt(meta['delivery_key'])
    assert receipt is not None
    assert receipt['delivery_phase'] == 'finalized'
    assert receipt['external_id'] == '888'
    assert receipt['metadata']['mode'] == 'queued_worker'
    assert state.is_delivered(meta['delivery_key']) is True
