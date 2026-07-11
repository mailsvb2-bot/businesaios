from __future__ import annotations

from runtime._internal.effects_actions.telegram.messaging import _delivery_evidence


def test_finalized_message_delivery_emits_connector_evidence() -> None:
    evidence = _delivery_evidence(
        ok=True,
        meta={
            "external_id": "telegram-message-42",
            "delivery_key": "delivery-42",
            "delivery_finalized": True,
        },
    )

    assert evidence["source"] == "connector"
    assert evidence["status"] == "verified"
    assert evidence["confidence"] == 1.0
    assert evidence["external_refs"] == ["telegram-message-42", "delivery-42"]


def test_queued_message_delivery_emits_ledger_acceptance_evidence() -> None:
    evidence = _delivery_evidence(
        ok=True,
        meta={
            "mode": "queued",
            "delivery_phase": "accepted_for_delivery",
            "delivery_key": "delivery-queued-7",
            "delivery_finalized": False,
        },
    )

    assert evidence["source"] == "ledger"
    assert evidence["status"] == "observed"
    assert evidence["confidence"] == 1.0
    assert evidence["external_refs"] == ["delivery-queued-7"]


def test_failed_message_delivery_never_emits_positive_evidence() -> None:
    evidence = _delivery_evidence(ok=False, meta={"delivery_key": "delivery-failed"})

    assert evidence["status"] == "failed"
    assert evidence["confidence"] == 0.0
