from __future__ import annotations

from types import SimpleNamespace

from runtime.handler_impl.domains.payment_ops import handle_create_payment_and_send_link


class FakeEffects:
    def __init__(
        self,
        *,
        payment_ok: bool = True,
        delivery_ok: bool = True,
        payment_verified: bool | None = None,
    ) -> None:
        self.payment_ok = payment_ok
        self.delivery_ok = delivery_ok
        self.payment_verified = payment_ok if payment_verified is None else bool(payment_verified)
        self.sent: list[dict] = []
        self.payment_calls: list[dict] = []

    def capture_payment(self, **kwargs):
        self.payment_calls.append(dict(kwargs))
        return {
            "ok": self.payment_ok,
            "meta": {
                "yookassa": {
                    "id": "payment-42",
                    "status": "pending",
                    "confirmation": {"confirmation_url": "https://pay.example/payment-42"},
                }
            },
            "evidence": {
                "source": "payment_gateway",
                "verified": self.payment_verified,
                "status": "verified" if self.payment_verified else "failed",
                "external_refs": ["payment-42"] if self.payment_verified else [],
                "confidence": 1.0 if self.payment_verified else 0.0,
            },
        }

    def send_message(self, **kwargs):
        self.sent.append(dict(kwargs))
        return {
            "ok": self.delivery_ok,
            "evidence": {
                "source": "connector",
                "verified": self.delivery_ok,
                "status": "verified" if self.delivery_ok else "failed",
                "external_refs": ["telegram-message-42"] if self.delivery_ok else [],
                "confidence": 1.0 if self.delivery_ok else 0.0,
            },
        }


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-pay-link-1",
            correlation_id="correlation-pay-link-1",
            tenant_id="business-a",
        )
    )


def _payload() -> dict[str, object]:
    return {
        "tenant_id": "business-a",
        "product_id": "crm-pro",
        "order_id": "order-42",
        "user_id": "user-1",
        "amount": 1500,
        "currency": "RUB",
        "provider": "yookassa",
    }


def test_payment_link_flow_preserves_confirmation_url_causality_and_both_evidence_sources() -> None:
    effects = FakeEffects(payment_ok=True, delivery_ok=True)

    result = handle_create_payment_and_send_link(_payload(), effects, _env())

    assert result["ok"] is True
    assert effects.sent[0]["text"] == "Ссылка на оплату: https://pay.example/payment-42"
    assert effects.sent[0]["tenant_id"] == "business-a"
    assert effects.sent[0]["priority"] == "high"
    assert effects.sent[0]["critical"] is True
    assert effects.payment_calls[0]["metadata"] == {
        "tenant_id": "business-a",
        "product_id": "crm-pro",
        "order_id": "order-42",
    }
    snapshots = result["feedback"]["connector_snapshots"]
    assert [item["source"] for item in snapshots] == ["payment_gateway", "connector"]
    assert result["router_evidence"]["external_refs"] == ["telegram-message-42"]


def test_payment_link_flow_is_not_successful_and_exposes_no_positive_evidence_when_user_delivery_fails() -> None:
    effects = FakeEffects(payment_ok=True, delivery_ok=False)

    result = handle_create_payment_and_send_link(_payload(), effects, _env())

    assert result["ok"] is False
    assert result["payment"]["ok"] is True
    assert result["delivery"]["ok"] is False
    assert result["router_evidence"] is None
    assert result["feedback"]["connector_snapshots"] == []


def test_payment_link_flow_is_not_successful_when_payment_creation_fails() -> None:
    effects = FakeEffects(payment_ok=False, delivery_ok=True)

    result = handle_create_payment_and_send_link(_payload(), effects, _env())

    assert result["ok"] is False
    assert result["payment"]["ok"] is False
    assert result["delivery"]["ok"] is True
    assert result["router_evidence"] is None
    assert result["feedback"]["connector_snapshots"] == []


def test_payment_link_flow_rejects_ok_payment_without_positive_provider_proof() -> None:
    effects = FakeEffects(payment_ok=True, delivery_ok=True, payment_verified=False)

    result = handle_create_payment_and_send_link(_payload(), effects, _env())

    assert result["payment"]["ok"] is True
    assert result["payment_evidence"]["verified"] is False
    assert result["delivery_evidence"]["verified"] is True
    assert result["ok"] is False
    assert result["router_evidence"] is None
    assert result["feedback"]["connector_snapshots"] == []
