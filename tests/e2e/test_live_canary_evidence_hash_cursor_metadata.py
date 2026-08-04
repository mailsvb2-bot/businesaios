from __future__ import annotations

from runtime.experiments.live_canary import source_event_evidence_ref


def test_append_cursor_metadata_does_not_change_evidence_hash() -> None:
    source_event = {
        "source": "booking_webhook",
        "event_type": "booking_confirmed@v1",
        "timestamp_ms": 1_000,
        "decision_id": "decision-1",
        "correlation_id": "correlation-1",
        "payload": {"success": True, "amount": 100.0},
    }

    assert source_event_evidence_ref(source_event) == source_event_evidence_ref(
        {**source_event, "append_seq": 77}
    )


def test_all_supported_cursor_aliases_are_transport_only() -> None:
    source_event = {
        "source": "provider",
        "event_type": "purchase_success",
        "timestamp_ms": 2_000,
        "decision_id": "decision-2",
        "correlation_id": "correlation-2",
        "payload": {"status": "succeeded", "amount": 250.0},
    }
    expected = source_event_evidence_ref(source_event)

    for key in ("append_seq", "event_sequence", "sequence_id"):
        assert source_event_evidence_ref({**source_event, key: 9}) == expected
