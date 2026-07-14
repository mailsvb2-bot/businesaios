from __future__ import annotations

import uuid

import pytest

from runtime._internal.effects_domains import admin_pricing_requests as admin_pricing_governance
from runtime._internal.effects_domains import admin_state
from runtime._internal.effects_domains.admin_state import AdminStateEffectsMixin


class FakeEventLog:
    def __init__(self, *, tenant_id: str = "business-a", events: list[dict] | None = None) -> None:
        self.tenant_id = tenant_id
        self.events = list(events or [])

    def iter_events(self):
        return iter(self.events)

    def emit(self, **event):
        row = {
            "event_id": str(event.get("event_id") or uuid.uuid4()),
            "tenant_id": self.tenant_id,
            "timestamp_ms": len(self.events) + 1,
            **dict(event),
        }
        self.events.append(row)
        return row


class FakeEffects(AdminStateEffectsMixin):
    def __init__(self, events: list[dict] | None = None) -> None:
        self.event_log = FakeEventLog(events=events)


def _request_event(
    *,
    request_id: str = "request-1",
    requested_by: str = "requester-1",
    product_id: str = "crm-pro",
    new_price: int = 900,
) -> dict:
    return {
        "event_id": f"event-request-{request_id}",
        "tenant_id": "business-a",
        "event_type": "admin_pricing_change_requested",
        "source": "admin_state",
        "user_id": requested_by,
        "decision_id": "decision-request",
        "correlation_id": "correlation-request",
        "timestamp_ms": 1,
        "payload": {
            "tenant_id": "business-a",
            "product_id": product_id,
            "environment": "test",
            "offer_id": "crm-pro-monthly",
            "plan_id": None,
            "new_price": int(new_price),
            "request_id": request_id,
            "suggested_pricing_version": "version-new",
            "reason": "test",
        },
    }


def _rejection_event(*, request_id: str = "request-1") -> dict:
    return {
        "event_id": f"event-reject-{request_id}",
        "tenant_id": "business-a",
        "event_type": "admin_pricing_change_rejected",
        "source": "admin_state",
        "user_id": "approver-1",
        "decision_id": "decision-reject",
        "correlation_id": "correlation-reject",
        "timestamp_ms": 2,
        "payload": {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "request_id": request_id,
            "reason": "bad economics",
        },
    }


def _applied_event(*, request_id: str = "request-1") -> dict:
    return {
        "event_id": f"event-applied-{request_id}",
        "tenant_id": "business-a",
        "event_type": "admin_pricing_change_applied",
        "source": "admin_state",
        "user_id": "approver-1",
        "decision_id": "decision-apply",
        "correlation_id": "correlation-apply",
        "timestamp_ms": 2,
        "payload": {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "environment": "test",
            "catalog_id": "business-a:crm-pro:test",
            "offer_id": "crm-pro-monthly",
            "plan_id": None,
            "old_price": 100,
            "new_price": 900,
            "pricing_version": "version-new",
            "request_id": request_id,
            "requested_by": "requester-1",
            "reason": "test",
        },
    }


def _apply(effects: FakeEffects, *, admin_id: str = "approver-1", product_id: str = "crm-pro", new_price: int = 900):
    return effects.apply_pricing_change(
        decision_id="decision-apply-new",
        correlation_id="correlation-apply-new",
        admin_id=admin_id,
        tenant_id="business-a",
        product_id=product_id,
        environment="test",
        offer_id="crm-pro-monthly",
        new_price=new_price,
        pricing_version="version-new",
        request_id="request-1",
        reason="test",
    )


@pytest.fixture(autouse=True)
def _disable_executor_guard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(admin_state, "assert_called_from_executor", lambda: None)


def test_apply_without_durable_request_is_rejected_before_catalog_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    effects = FakeEffects()
    mutation_calls = 0

    def fake_apply(*args, **kwargs):
        nonlocal mutation_calls
        mutation_calls += 1
        raise AssertionError("pricing mutation must not be reached")

    monkeypatch.setattr(admin_state, "apply_pricing_change_effect", fake_apply)

    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUEST_NOT_FOUND:business-a:request-1"):
        _apply(effects)

    assert mutation_calls == 0


def test_requester_cannot_self_approve_by_omitting_requested_by(monkeypatch: pytest.MonkeyPatch) -> None:
    effects = FakeEffects(events=[_request_event(requested_by="admin-1")])
    mutation_calls = 0
    monkeypatch.setattr(admin_pricing_governance, "env_bool", lambda *_args, **_kwargs: False)

    def fake_apply(*args, **kwargs):
        nonlocal mutation_calls
        mutation_calls += 1
        raise AssertionError("pricing mutation must not be reached")

    monkeypatch.setattr(admin_state, "apply_pricing_change_effect", fake_apply)

    with pytest.raises(RuntimeError, match="SELF_APPROVAL_FORBIDDEN"):
        _apply(effects, admin_id="admin-1")

    assert mutation_calls == 0


def test_apply_scope_must_match_original_request_exactly(monkeypatch: pytest.MonkeyPatch) -> None:
    effects = FakeEffects(events=[_request_event()])
    mutation_calls = 0

    def fake_apply(*args, **kwargs):
        nonlocal mutation_calls
        mutation_calls += 1
        raise AssertionError("pricing mutation must not be reached")

    monkeypatch.setattr(admin_state, "apply_pricing_change_effect", fake_apply)

    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUEST_MISMATCH:request-1"):
        _apply(effects, product_id="different-product")
    with pytest.raises(RuntimeError, match="PRICING_CHANGE_REQUEST_MISMATCH:request-1"):
        _apply(effects, new_price=901)

    assert mutation_calls == 0


def test_rejected_request_cannot_be_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    effects = FakeEffects(events=[_request_event(), _rejection_event()])
    mutation_calls = 0

    def fake_apply(*args, **kwargs):
        nonlocal mutation_calls
        mutation_calls += 1
        raise AssertionError("pricing mutation must not be reached")

    monkeypatch.setattr(admin_state, "apply_pricing_change_effect", fake_apply)

    with pytest.raises(RuntimeError, match="PRICING_REQUEST_REJECTED:request-1"):
        _apply(effects)

    assert mutation_calls == 0


def test_applied_request_retry_returns_existing_ledger_proof_without_second_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    effects = FakeEffects(events=[_request_event(), _applied_event()])
    mutation_calls = 0

    def fake_apply(*args, **kwargs):
        nonlocal mutation_calls
        mutation_calls += 1
        raise AssertionError("pricing mutation must not be reached")

    monkeypatch.setattr(admin_state, "apply_pricing_change_effect", fake_apply)

    result = _apply(effects)

    assert mutation_calls == 0
    assert result["ok"] is True
    assert result["replayed"] is True
    assert result["router_evidence"]["source"] == "ledger"
    assert result["router_evidence"]["external_refs"] == ["event-applied-request-1"]


def test_same_request_id_cannot_be_reused_for_different_price() -> None:
    effects = FakeEffects(events=[_request_event()])

    with pytest.raises(RuntimeError, match="PRICING_REQUEST_SCOPE_MISMATCH:request-1"):
        effects.request_pricing_change(
            decision_id="decision-request-2",
            correlation_id="correlation-request-2",
            admin_id="requester-1",
            tenant_id="business-a",
            product_id="crm-pro",
            environment="test",
            offer_id="crm-pro-monthly",
            new_price=901,
            request_id="request-1",
            suggested_pricing_version="version-new",
            reason="different",
        )


def test_exact_request_retry_reuses_existing_request_event() -> None:
    effects = FakeEffects(events=[_request_event()])

    result = effects.request_pricing_change(
        decision_id="decision-request-2",
        correlation_id="correlation-request-2",
        admin_id="requester-1",
        tenant_id="business-a",
        product_id="crm-pro",
        environment="test",
        offer_id="crm-pro-monthly",
        new_price=900,
        request_id="request-1",
        suggested_pricing_version="version-new",
        reason="test",
    )

    assert result["replayed"] is True
    assert len(effects.event_log.events) == 1
    assert result["router_evidence"]["external_refs"] == ["event-request-request-1"]


def test_already_applied_request_cannot_be_rejected() -> None:
    effects = FakeEffects(events=[_request_event(), _applied_event()])

    with pytest.raises(RuntimeError, match="PRICING_REQUEST_ALREADY_APPLIED:request-1"):
        effects.reject_pricing_change(
            decision_id="decision-reject-new",
            correlation_id="correlation-reject-new",
            admin_id="approver-2",
            tenant_id="business-a",
            product_id="crm-pro",
            request_id="request-1",
            reason="too late",
        )
