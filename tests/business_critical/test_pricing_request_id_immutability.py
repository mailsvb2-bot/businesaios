from __future__ import annotations

from typing import Any

import pytest

from runtime._internal.effects_domains import admin_state
from runtime._internal.effects_domains.admin_pricing_requests import (
    assert_pricing_request_id_available,
    resolve_pricing_change_request,
)


class FakeEventLog:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._tenant_id = "business-a"
        self.events = list(events)

    def iter_events(self):
        return iter(self.events)


def _request_event(*, price: int = 900) -> dict[str, Any]:
    return {
        "event_type": "admin_pricing_change_requested",
        "user_id": "requester-admin",
        "payload": {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "environment": "test",
            "offer_id": "crm-pro-monthly",
            "plan_id": 1,
            "new_price": int(price),
            "request_id": "request-immutable",
            "suggested_pricing_version": "version-approved",
        },
    }


def test_existing_request_id_cannot_be_registered_again() -> None:
    event_log = FakeEventLog([_request_event()])

    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUEST_ID_ALREADY_EXISTS"):
        assert_pricing_request_id_available(
            event_log,
            tenant_id="business-a",
            request_id="request-immutable",
        )


def test_duplicated_historical_request_id_fails_closed_during_resolution() -> None:
    event_log = FakeEventLog([_request_event(price=900), _request_event(price=9000)])

    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUEST_ID_NOT_UNIQUE"):
        resolve_pricing_change_request(
            event_log,
            tenant_id="business-a",
            request_id="request-immutable",
        )


def test_admin_mixin_rejects_conflicting_request_before_effect_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = admin_state.AdminStateEffectsMixin()
    owner.event_log = FakeEventLog([_request_event()])
    monkeypatch.setattr(admin_state, "assert_called_from_executor", lambda: None)

    called = False

    def fake_request(_owner: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(admin_state, "request_pricing_change_effect", fake_request)

    with pytest.raises(RuntimeError, match="PRICING_REQUEST_SCOPE_MISMATCH"):
        owner.request_pricing_change(
            decision_id="decision-request",
            correlation_id="correlation-request",
            admin_id="requester-admin",
            tenant_id="business-a",
            product_id="crm-pro",
            environment="test",
            offer_id="crm-pro-monthly",
            plan_id=1,
            new_price=9000,
            request_id="request-immutable",
            suggested_pricing_version="version-new",
        )

    assert called is False
