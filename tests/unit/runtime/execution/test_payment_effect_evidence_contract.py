from __future__ import annotations

import pytest

from runtime._internal.effects_actions.payments import selection as selection_module
from runtime._internal.effects_actions.payments.selection import (
    _payment_gateway_evidence,
    capture_payment_effect,
)


class FakeEventLog:
    tenant_id = "business-a"

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, **event) -> None:
        self.events.append(dict(event))


class FakeEffects:
    def __init__(self, provider_result) -> None:
        self.event_log = FakeEventLog()
        self.provider_result = provider_result

    def _yookassa_create_payment(self, **_kwargs):
        return self.provider_result


def test_valid_provider_payment_id_emits_gateway_evidence() -> None:
    evidence = _payment_gateway_evidence(
        ok=True,
        external_id="payment-42",
        provider="yookassa",
        meta={"yookassa": {"status": "pending"}},
        business_metadata={
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "order_id": "order-42",
        },
    )

    assert evidence["source"] == "payment_gateway"
    assert evidence["status"] == "verified"
    assert evidence["external_refs"] == ["payment-42"]
    assert evidence["confidence"] == 1.0
    assert evidence["payload"]["provider_status"] == "pending"
    assert evidence["payload"]["tenant_id"] == "business-a"
    assert evidence["payload"]["product_id"] == "crm-pro"
    assert evidence["payload"]["order_id"] == "order-42"


def test_success_without_valid_provider_id_never_emits_positive_payment_evidence() -> None:
    evidence = _payment_gateway_evidence(
        ok=True,
        external_id=None,
        provider="yookassa",
        meta={"yookassa": {"status": "pending"}},
        business_metadata={},
    )

    assert evidence["status"] == "failed"
    assert evidence["external_refs"] == []
    assert evidence["confidence"] == 0.0


def test_provider_failure_never_emits_positive_payment_evidence() -> None:
    evidence = _payment_gateway_evidence(
        ok=False,
        external_id="payment-should-not-verify",
        provider="yookassa",
        meta={"yookassa": {"status": "failed"}},
        business_metadata={},
    )

    assert evidence["status"] == "failed"
    assert evidence["confidence"] == 0.0


def test_provider_ok_without_external_id_fails_the_payment_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(selection_module, "assert_called_from_executor", lambda: None)
    effects = FakeEffects((True, {"yookassa": {"status": "pending"}}))

    result = capture_payment_effect(
        effects,
        decision_id="decision-payment",
        correlation_id="correlation-payment",
        user_id="user-1",
        amount=1500,
        currency="RUB",
        provider="yookassa",
        metadata={
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "order_id": "order-1",
        },
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["router_evidence"] is None
    assert result["evidence"]["status"] == "failed"
    assert [event["event_type"] for event in effects.event_log.events] == [
        "payment_create_attempted",
        "payment_create_failed",
    ]
