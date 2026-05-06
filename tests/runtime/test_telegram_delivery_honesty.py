from __future__ import annotations

from runtime._internal.effects_actions.telegram.messaging_parts.transport import telegram_delivery
from runtime.messaging.outbound_message import OutboundMessage
from runtime.platform.delivery_state import DeliveryState


class _DummyEventLog:
    def emit(self, **kwargs):
        return None


class _QueuedSelf:
    def __init__(self, state):
        self.delivery_state = state
        self.event_log = _DummyEventLog()
        self.telegram_outbound_queue = object()
        self._last_sent = {}

    def _telegram_send_message(self, **kwargs):
        return True, {'mode': 'queued', 'channel': 'telegram'}


class _DirectSelf:
    def __init__(self, state):
        self.delivery_state = state
        self.event_log = _DummyEventLog()
        self.telegram_outbound_queue = None
        self._last_sent = {}

    def _telegram_send_message(self, **kwargs):
        return True, {'mode': 'direct', 'channel': 'telegram', 'external_id': '555'}


def test_queued_transport_does_not_mark_delivery_finalized(tmp_path) -> None:
    state = DeliveryState(db_path=tmp_path / 'queued.sqlite')
    owner = _QueuedSelf(state)
    msg = OutboundMessage(decision_id='d1', correlation_id='c1', tenant_id='t1', user_id='42', channel='telegram', text='hello')

    ok, meta = telegram_delivery(owner, msg=msg)

    assert ok is True
    assert meta['mode'] == 'queued'
    assert meta['delivery_finalized'] is False
    assert state.is_delivered(msg.delivery_key) is False


def test_direct_transport_marks_delivery_finalized(tmp_path) -> None:
    state = DeliveryState(db_path=tmp_path / 'direct.sqlite')
    owner = _DirectSelf(state)
    msg = OutboundMessage(decision_id='d1', correlation_id='c1', tenant_id='t1', user_id='42', channel='telegram', text='hello')

    ok, meta = telegram_delivery(owner, msg=msg)

    assert ok is True
    assert meta['delivery_finalized'] is True
    assert state.is_delivered(msg.delivery_key) is True
    receipt = state.get_receipt(msg.delivery_key)
    assert receipt is not None
    assert receipt['external_id'] == '555'
