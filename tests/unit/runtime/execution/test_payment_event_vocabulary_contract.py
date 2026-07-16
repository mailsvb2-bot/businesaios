from __future__ import annotations

from core.events.event_types import (
    KNOWN_EVENT_TYPES,
    PAYMENT_CAPTURED,
    PAYMENT_CHECKED,
    PAYMENT_CREATED,
    PAYMENT_CREATE_ATTEMPTED,
    PAYMENT_CREATE_FAILED,
    PAYMENT_FAILED,
    PAYMENT_SUCCEEDED,
    PAYMENTS_RECONCILED,
    PAYMENTS_RECONCILE_FAILED,
    is_known,
)


def test_canonical_payment_proof_lifecycle_is_strict_event_safe() -> None:
    required = {
        PAYMENT_CREATE_ATTEMPTED,
        PAYMENT_CREATED,
        PAYMENT_CREATE_FAILED,
        PAYMENT_CHECKED,
        PAYMENT_CAPTURED,
        PAYMENT_SUCCEEDED,
        PAYMENT_FAILED,
        PAYMENTS_RECONCILED,
        PAYMENTS_RECONCILE_FAILED,
    }

    assert required <= KNOWN_EVENT_TYPES
    assert all(is_known(event_type) for event_type in required)


def test_payment_captured_remains_explicit_canonical_proof_event() -> None:
    assert PAYMENT_CAPTURED == "payment_captured"
    assert PAYMENT_CAPTURED in KNOWN_EVENT_TYPES
