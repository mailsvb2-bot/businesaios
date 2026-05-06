from __future__ import annotations

from runtime.platform.delivery_state import DeliveryState


def test_delivery_state_lists_only_non_finalized_receipts(tmp_path) -> None:
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    state.mark_accepted('msg-a', payload_digest='aaa', metadata={'mode': 'queued'})
    state.mark_delivered('msg-b', external_id='2', payload_digest='bbb', metadata={'mode': 'direct'})

    items = state.list_inflight_receipts(limit=10)

    assert [item['message_id'] for item in items] == ['msg-a']
    assert items[0]['delivery_phase'] == 'accepted_for_delivery'
    assert state.is_accepted('msg-a') is True
    assert state.is_accepted('msg-b') is False
