from __future__ import annotations

from typing import Any

import pytest

from runtime._internal.effects_domains import admin_state
from runtime._internal.effects_domains.admin_pricing_requests import (
    assert_pricing_request_open,
    resolve_pricing_change_request,
    validate_pricing_apply_against_request,
)


class FakeEventLog:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._tenant_id = "business-a"
        self.events = list(events)

    def iter_events(self):
        return iter(self.events)


def _request_event(*, tenant: str = "business-a", request_id: str = "request-1") -> dict[str, Any]:
    return {
        "event_type": "admin_pricing_change_requested",
        "user_id": "requester-admin",
        "payload": {
            "tenant_id": tenant,
            "product_id": "crm-pro",
            "environment": "test",
            "offer_id": "crm-pro-monthly",
            "plan_id": 1,
            "new_price": 900,
            "request_id": request_id,
            "suggested_pricing_version": "version-approved",
        },
    }


def _validate(event_log: FakeEventLog, **overrides: Any):
    kwargs = {
        "tenant_id": "business-a",
        "request_id": "request-1",
        "product_id": "crm-pro",
        "environment": "test",
        "offer_id": "crm-pro-monthly",
        "plan_id": 1,
        "new_price": 900,
        "pricing_version": "version-approved",
    }
    kwargs.update(overrides)
    return validate_pricing_apply_against_request(event_log, **kwargs)


def test_exact_pricing_request_resolves_original_requester() -> None:
    event_log = FakeEventLog([_request_event()])

    request = _validate(event_log)

    assert request.request_id == "request-1"
    assert request.requested_by == "requester-admin"
    assert request.tenant_id == "business-a"
    assert request.product_id == "crm-pro"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("product_id", "other-product"),
        ("environment", "prod"),
        ("offer_id", "other-offer"),
        ("plan_id", 2),
        ("new_price", 9000),
        ("pricing_version", "different-version"),
    ),
)
def test_pricing_approval_cannot_change_recorded_request(field: str, value: Any) -> None:
    event_log = FakeEventLog([_request_event()])

    with pytest.raises(RuntimeError, match=f"PRICING_CHANGE_REQUEST_MISMATCH:request-1:.*{field}"):
        _validate(event_log, **{field: value})


def test_same_request_id_from_another_tenant_is_not_visible() -> None:
    event_log = FakeEventLog([_request_event(tenant="business-b")])

    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUEST_NOT_FOUND"):
        resolve_pricing_change_request(
            event_log,
            tenant_id="business-a",
            request_id="request-1",
        )


def test_already_resolved_pricing_request_cannot_be_applied_twice() -> None:
    event_log = FakeEventLog(
        [
            _request_event(),
            {
                "event_type": "admin_pricing_change_applied",
                "payload": {
                    "tenant_id": "business-a",
                    "request_id": "request-1",
                },
            },
        ]
    )

    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUEST_ALREADY_RESOLVED"):
        assert_pricing_request_open(
            event_log,
            tenant_id="business-a",
            request_id="request-1",
        )


def test_mixin_uses_recorded_requester_and_rejects_spoofed_requested_by(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_log = FakeEventLog([_request_event()])
    owner = admin_state.AdminStateEffectsMixin()
    owner.event_log = event_log
    monkeypatch.setattr(admin_state, "assert_called_from_executor", lambda: None)

    captured: dict[str, Any] = {}

    def fake_apply(_owner: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(admin_state, "apply_pricing_change_effect", fake_apply)

    result = owner.apply_pricing_change(
        decision_id="decision-apply",
        correlation_id="correlation-apply",
        admin_id="approver-admin",
        tenant_id="business-a",
        product_id="crm-pro",
        environment="test",
        offer_id="crm-pro-monthly",
        plan_id=1,
        new_price=900,
        pricing_version="version-approved",
        request_id="request-1",
    )

    assert result == {"ok": True}
    assert captured["requested_by"] == "requester-admin"

    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUESTER_MISMATCH"):
        owner.apply_pricing_change(
            decision_id="decision-spoof",
            correlation_id="correlation-spoof",
            admin_id="approver-admin",
            tenant_id="business-a",
            product_id="crm-pro",
            environment="test",
            offer_id="crm-pro-monthly",
            plan_id=1,
            new_price=900,
            pricing_version="version-approved",
            request_id="request-1",
            requested_by="fake-requester",
        )
