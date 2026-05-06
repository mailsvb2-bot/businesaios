from __future__ import annotations

from pathlib import Path

from runtime.platform.delivery_state import DeliveryState


def test_delivery_state_tracks_accepted_then_finalized(tmp_path: Path) -> None:
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')

    state.mark_accepted('msg-1', payload_digest='abc123', metadata={'mode': 'queued'})
    accepted = state.get_receipt('msg-1')
    assert accepted is not None
    assert accepted['delivery_phase'] == 'accepted_for_delivery'
    assert accepted['accepted_at_ms'] is not None
    assert accepted['finalized_at_ms'] is None
    assert state.is_delivered('msg-1') is False

    state.mark_delivered('msg-1', external_id='tg-1', payload_digest='abc123', metadata={'mode': 'direct'})
    finalized = state.get_receipt('msg-1')
    assert finalized is not None
    assert finalized['delivery_phase'] == 'finalized'
    assert finalized['accepted_at_ms'] is not None
    assert finalized['finalized_at_ms'] is not None
    assert finalized['metadata']['mode'] == 'direct'
    assert state.is_delivered('msg-1') is True


def test_delivery_state_preserves_finalized_phase_against_late_acceptance(tmp_path: Path) -> None:
    state = DeliveryState(db_path=tmp_path / 'delivery.sqlite')
    state.mark_delivered('msg-1', external_id='tg-1', payload_digest='abc123', metadata={'mode': 'direct'})
    state.mark_accepted('msg-1', payload_digest='abc123', metadata={'mode': 'queued'})

    receipt = state.get_receipt('msg-1')
    assert receipt is not None
    assert receipt['delivery_phase'] == 'finalized'
    assert receipt['external_id'] == 'tg-1'
    assert state.is_delivered('msg-1') is True
