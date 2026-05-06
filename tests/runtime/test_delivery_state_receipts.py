from __future__ import annotations

from pathlib import Path

from runtime.platform.delivery_state import DeliveryState


def test_delivery_state_persists_receipt_metadata(tmp_path: Path) -> None:
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    state.mark_delivered('msg-1', external_id='tg-101', payload_digest='abc123', metadata={'mode': 'direct', 'channel': 'telegram'})

    assert state.is_delivered('msg-1') is True
    receipt = state.get_receipt('msg-1')
    assert receipt is not None
    assert receipt['external_id'] == 'tg-101'
    assert receipt['payload_digest'] == 'abc123'
    assert receipt['metadata']['mode'] == 'direct'
    assert receipt['metadata']['channel'] == 'telegram'
