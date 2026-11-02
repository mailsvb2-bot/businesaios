"""Direct PSP creation and message delivery must be executor-owned."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime._internal.effects_actions.payments import yookassa
from runtime._internal.effects_actions.telegram import messaging
from runtime._internal.effects_actions.telegram_actions import TelegramEffectsMixin
from runtime.execution.context import executor_context


def _send_message():
    return messaging.send_message_effect(
        object(), decision_id="d1", correlation_id="c1", user_id="u1", text="hello",
    )


def test_direct_message_delivery_and_mixin_refuse_non_executor_calls(monkeypatch):
    monkeypatch.setattr(
        messaging, "build_outbound_message",
        lambda **kwargs: pytest.fail("untrusted call built a message"),
    )
    with pytest.raises(RuntimeError, match="SIDE_EFFECT_REQUIRES_EXECUTOR"):
        _send_message()
    with pytest.raises(RuntimeError, match="SIDE_EFFECT_REQUIRES_EXECUTOR"):
        TelegramEffectsMixin().send_message(
            decision_id="d1", correlation_id="c1", user_id="u1", text="hello",
        )


def test_direct_payment_creation_refuses_non_executor_calls(monkeypatch):
    monkeypatch.setattr(
        yookassa, "execute_effect_action_sync",
        lambda *args, **kwargs: pytest.fail("untrusted call reached PSP"),
    )
    with pytest.raises(RuntimeError, match="SIDE_EFFECT_REQUIRES_EXECUTOR"):
        yookassa.yookassa_create_payment(
            effects=object(), decision_id="d1", amount=100,
            currency="RUB", user_id="u1",
        )


def test_authorized_executor_still_reaches_canonical_message_delivery(monkeypatch):
    msg = SimpleNamespace(
        decision_id="d1", correlation_id="c1", user_id="u1", text="hello",
        channel="telegram", track_event_type=None, track_payload=None,
    )
    monkeypatch.setattr(messaging, "build_outbound_message", lambda **kwargs: msg)
    monkeypatch.setattr(messaging, "build_single_sender", lambda effects: None)
    monkeypatch.setattr(
        messaging, "execute_delivery_path",
        lambda *args, **kwargs: (True, {"policy": {"selected_channel": "telegram"}}),
    )
    monkeypatch.setattr(messaging, "track_delivery", lambda *args, **kwargs: None)
    monkeypatch.setattr(messaging, "track_business_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(messaging, "build_delivery_evidence", lambda **kwargs: {"verified": True})
    with executor_context():
        result = _send_message()
    assert result["ok"] is True
    assert result["evidence"] == {"verified": True}


def test_authorized_executor_still_reaches_canonical_psp_action(monkeypatch):
    seen = []
    def fake_action(effects, action, payload):
        seen.append((effects, action, payload))
        return {"ok": True, "external_id": "payment-1"}

    monkeypatch.setattr(yookassa, "execute_effect_action_sync", fake_action)
    with executor_context():
        ok, result = yookassa.yookassa_create_payment(
            effects=object(), decision_id="d1", amount=123,
            currency="RUB", user_id="u1", metadata={"order_id": "o1"},
        )
    assert ok and result["external_id"] == "payment-1"
    assert len(seen) == 1 and seen[0][2]["customer_id"] == "u1"
