from __future__ import annotations

from runtime._internal.effects_actions.payments.selection import _payment_gateway_evidence


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
