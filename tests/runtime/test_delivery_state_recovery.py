from __future__ import annotations

from runtime.platform.delivery_state import ACCEPTED_PHASE, RECOVERY_PHASE, DeliveryState


def test_delivery_state_lists_stale_accepted_receipts_and_marks_recovery(tmp_path) -> None:
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    state.mark_accepted(
        'msg-1',
        payload_digest='abc123',
        metadata={
            'method': 'sendMessage',
            'chat_id': '42',
            'payload': {'chat_id': '42', 'text': 'hello'},
            'timeout_s': 30,
            'priority': 'normal',
            'critical': True,
            'mode': 'queued',
        },
    )

    receipt = state.get_receipt('msg-1')
    assert receipt is not None
    stale = state.list_stale_accepted_receipts(older_than_ms=0, limit=10, now_ms=receipt['accepted_at_ms'])
    assert [item['message_id'] for item in stale] == ['msg-1']
    assert stale[0]['delivery_phase'] == ACCEPTED_PHASE

    recovered = state.mark_recovery_queued(
        'msg-1',
        payload_digest='abc123',
        metadata={
            'payload': {'chat_id': '42', 'text': 'hello'},
            'timeout_s': 30,
            'priority': 'normal',
            'critical': True,
            'recovery_reason': 'stale_accepted_receipt',
        },
        now_ms=(receipt['accepted_at_ms'] or 0) + 123,
    )
    assert recovered is not None
    assert recovered['delivery_phase'] == RECOVERY_PHASE
    assert recovered['metadata']['recovery'] is True
    assert recovered['metadata']['recovery_attempts'] == 1
    assert recovered['metadata']['last_recovery_at_ms'] == (receipt['accepted_at_ms'] or 0) + 123
    assert recovered['metadata']['payload'] == {'chat_id': '42', 'text': 'hello'}
    assert recovered['metadata']['timeout_s'] == 30
    assert recovered['metadata']['priority'] == 'normal'
    assert recovered['metadata']['critical'] is True
