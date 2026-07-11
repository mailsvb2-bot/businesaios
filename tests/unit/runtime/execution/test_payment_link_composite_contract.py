from __future__ import annotations

from types import SimpleNamespace

from runtime.handler_impl.domains.payment_ops import handle_create_payment_and_send_link


class FakeEffects:
    def __init__(self, *, payment_ok: bool = True, delivery_ok: bool = True) -> None:
        self.payment_ok = payment_ok
        self.delivery_ok = delivery_ok
        self.sent: list[dict] = []

    def capture_payment(self, **kwargs):
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
                "verified": self.payment_ok,
                "status": "verified" if self.payment_ok else "failed",
                "external_refs": ["payment-42"] if self.payment_ok else [],
                "confidence": 1.0 if self.payment_ok else 0.0,
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
        )
    )


def _payload() -> dict[str, object]:
    return {
        "user_id": "user-1",
        "amount": 1500,
        "currency": "RUB",
        "provider": "yookassa",
    }


def test_payment_link_flow_preserves_confirmation_url_and_both_evidence_sources() -> None:
    effects = FakeEffects(payment_ok=True, delivery_ok=True)

    result = handle_create_payment_and_send_link(_payload(), effects, _env())

    assert result["ok"] is True
    assert effects.sent[0]["text"] == "Ссылка на оплату: https://pay.example/payment-42"
    assert effects.sent[0]["priority"] == "high"
    assert effects.sent[0]["critical"] is True
    snapshots = result["feedback"]["connector_snapshots"]
    assert [item["source"] for item in snapshots] == ["payment_gateway", "connector"]
    assert result["evidence"]["external_refs"] == ["telegram-message-42"]


def test_payment_link_flow_is_not_successful_when_user_delivery_fails() -> None:
    effects = FakeEffects(payment_ok=True, delivery_ok=False)

    result = handle_create_payment_and_send_link(_payload(), effects, _env())

    assert result["ok"] is False
    assert result["payment"]["ok"] is True
    assert result["delivery"]["ok"] is False


def test_payment_link_flow_is_not_successful_when_payment_creation_fails() -> None:
    effects = FakeEffects(payment_ok=False, delivery_ok=True)

    result = handle_create_payment_and_send_link(_payload(), effects, _env())

    assert result["ok"] is False
    assert result["payment"]["ok"] is False
    assert result["delivery"]["ok"] is True
