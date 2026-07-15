from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.handlers import ads_rl_train_tick
from runtime.handlers.ads_autopilot_tick_parts.messages import send_autopilot_message


class FakeEffects:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.events: list[dict] = []

    def send_message(self, **kwargs):
        self.messages.append(dict(kwargs))
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": ["message-ads-1"],
                "confidence": 1.0,
            },
        }

    def track_event(self, **kwargs):
        self.events.append(dict(kwargs))
        return {"ok": True}


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="signed-decision-ads",
            correlation_id="signed-correlation-ads",
        )
    )


@pytest.mark.lock
def test_autopilot_message_uses_tenant_user_and_signed_route_without_legacy_chat_id() -> None:
    effects = FakeEffects()

    result = send_autopilot_message(
        effects=effects,
        payload={
            "tenant_id": "business-a",
            "user_id": "owner-1",
            "decision_id": "spoofed-decision",
            "correlation_id": "spoofed-correlation",
            "channel": "instagram",
            "channel_policy": {"fallback_channels": ["messenger", "email"]},
        },
        decision_id="signed-decision-ads",
        correlation_id="signed-correlation-ads",
        text="Plan ready",
        track_event_type="ads_autopilot_tick@v1",
        track_payload={"status": "ok"},
    )

    assert result["ok"] is True
    call = effects.messages[-1]
    assert call["decision_id"] == "signed-decision-ads"
    assert call["correlation_id"] == "signed-correlation-ads"
    assert call["tenant_id"] == "business-a"
    assert call["user_id"] == "owner-1"
    assert "chat_id" not in call
    assert call["channel"] == "instagram"
    assert call["channel_policy"] == {
        "fallback_channels": ["messenger", "email"]
    }
    assert call["track_payload"] == {
        "status": "ok",
        "tenant_id": "business-a",
    }


@pytest.mark.lock
def test_rl_train_skipped_branch_is_not_business_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effects = FakeEffects()
    monkeypatch.setattr(
        ads_rl_train_tick,
        "bind_runtime_state",
        lambda **_kwargs: None,
    )

    result = ads_rl_train_tick.handle_ads_rl_train_tick(
        {
            "tenant_id": "business-a",
            "user_id": "owner-1",
            "decision_id": "spoofed-decision",
            "correlation_id": "spoofed-correlation",
            "decision_ids": [],
            "channel": "whatsapp",
            "channel_policy": {"fallback_channels": ["sms", "email"]},
        },
        effects,
        _env(),
        event_store=object(),
    )

    assert result["ok"] is False
    assert result["status"] == "skipped"
    assert result["delivery"]["ok"] is True
    assert result["router_evidence"] is None
    call = effects.messages[-1]
    assert call["decision_id"] == "signed-decision-ads"
    assert call["correlation_id"] == "signed-correlation-ads"
    assert call["tenant_id"] == "business-a"
    assert call["user_id"] == "owner-1"
    assert "chat_id" not in call
    assert call["track_event_type"] == "ads_rl_train_skipped@v1"
    assert call["track_payload"]["tenant_id"] == "business-a"
    assert call["channel"] == "whatsapp"
    assert call["channel_policy"] == {"fallback_channels": ["sms", "email"]}


@pytest.mark.lock
@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"user_id": "owner-1"}, "TENANT_ID_REQUIRED"),
        ({"tenant_id": "business-a"}, "USER_ID_REQUIRED"),
    ],
)
def test_ads_delivery_fails_closed_without_business_identity(
    payload: dict[str, str],
    expected: str,
) -> None:
    with pytest.raises(RuntimeError, match=expected):
        send_autopilot_message(
            effects=FakeEffects(),
            payload=payload,
            decision_id="signed-decision-ads",
            correlation_id="signed-correlation-ads",
            text="Plan ready",
            track_event_type="ads_autopilot_tick@v1",
        )
