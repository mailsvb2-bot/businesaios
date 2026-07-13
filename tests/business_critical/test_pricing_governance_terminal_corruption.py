from __future__ import annotations

import pytest

from runtime._internal.effects_domains.admin_pricing_governance import (
    resolve_pricing_request_lifecycle,
)


class FakeEventLog:
    def __init__(self, events: list[dict]) -> None:
        self.events = list(events)

    def iter_events(self):
        return iter(self.events)


def _event(*, event_id: str, event_type: str, user_id: str, payload: dict) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "user_id": user_id,
        "decision_id": f"decision-{event_id}",
        "correlation_id": f"correlation-{event_id}",
        "timestamp_ms": 1,
        "payload": dict(payload),
    }


def _request() -> dict:
    return _event(
        event_id="request-event",
        event_type="admin_pricing_change_requested",
        user_id="requester-1",
        payload={
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "environment": "test",
            "offer_id": "crm-pro-monthly",
            "plan_id": None,
            "new_price": 900,
            "request_id": "request-1",
            "suggested_pricing_version": "version-new",
            "reason": "test",
        },
    )


def _rejected(*, event_id: str = "reject-event", user_id: str = "approver-1", reason: str = "bad economics") -> dict:
    return _event(
        event_id=event_id,
        event_type="admin_pricing_change_rejected",
        user_id=user_id,
        payload={
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "request_id": "request-1",
            "reason": reason,
        },
    )


def _applied(*, event_id: str = "apply-event", user_id: str = "approver-1", new_price: int = 900) -> dict:
    return _event(
        event_id=event_id,
        event_type="admin_pricing_change_applied",
        user_id=user_id,
        payload={
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "environment": "test",
            "catalog_id": "business-a:crm-pro:test",
            "offer_id": "crm-pro-monthly",
            "plan_id": None,
            "old_price": 100,
            "new_price": new_price,
            "pricing_version": "version-new",
            "request_id": "request-1",
            "requested_by": "requester-1",
            "reason": "test",
        },
    )


@pytest.mark.lock
def test_request_cannot_be_both_rejected_and_applied() -> None:
    event_log = FakeEventLog([_request(), _rejected(), _applied()])

    with pytest.raises(RuntimeError, match="PRICING_REQUEST_TERMINAL_CONFLICT:request-1"):
        resolve_pricing_request_lifecycle(event_log, request_id="request-1")


@pytest.mark.lock
def test_conflicting_duplicate_applied_events_are_rejected() -> None:
    event_log = FakeEventLog(
        [
            _request(),
            _applied(event_id="apply-1", user_id="approver-1", new_price=900),
            _applied(event_id="apply-2", user_id="approver-2", new_price=901),
        ]
    )

    with pytest.raises(RuntimeError, match="PRICING_REQUEST_TERMINAL_CONFLICT:request-1"):
        resolve_pricing_request_lifecycle(event_log, request_id="request-1")


@pytest.mark.lock
def test_conflicting_duplicate_rejection_events_are_rejected() -> None:
    event_log = FakeEventLog(
        [
            _request(),
            _rejected(event_id="reject-1", user_id="approver-1", reason="bad economics"),
            _rejected(event_id="reject-2", user_id="approver-2", reason="different reason"),
        ]
    )

    with pytest.raises(RuntimeError, match="PRICING_REQUEST_TERMINAL_CONFLICT:request-1"):
        resolve_pricing_request_lifecycle(event_log, request_id="request-1")


@pytest.mark.lock
def test_identical_terminal_retry_is_not_treated_as_corruption() -> None:
    first = _applied(event_id="apply-1")
    retry = _applied(event_id="apply-2")
    event_log = FakeEventLog([_request(), first, retry])

    lifecycle = resolve_pricing_request_lifecycle(event_log, request_id="request-1")

    assert lifecycle.applied_event is not None
    assert lifecycle.rejected_event is None
    assert lifecycle.requested_by == "requester-1"
