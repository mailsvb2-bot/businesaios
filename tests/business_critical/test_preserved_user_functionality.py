from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime._internal.effects_actions.payments import access
from runtime.handler_impl.domains.user_ops import (
    handle_log_mood,
    handle_send_audio,
)


class FakeEffects:
    def __init__(self, event_log=None) -> None:
        self.event_log = event_log
        self.calls: list[tuple[str, dict]] = []

    def send_audio(self, **kwargs):
        self.calls.append(("send_audio", dict(kwargs)))
        return {"ok": True}

    def log_mood(self, **kwargs):
        self.calls.append(("log_mood", dict(kwargs)))
        return {"ok": True}

    def send_message(self, **kwargs):
        self.calls.append(("send_message", dict(kwargs)))
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
            },
        }


class FakeStore:
    def __init__(self, events: list[dict]) -> None:
        self.events = events

    def iter_events(self, **_kwargs):
        return list(self.events)


class FakeEventLog:
    tenant_id = "business-a"

    def __init__(self, events: list[dict]) -> None:
        self._store = FakeStore(events)
        self.events = events

    def emit(self, **event):
        normalized = {
            "event_type": event["event_type"],
            "payload": dict(event.get("payload") or {}),
            **dict(event),
        }
        self.events.append(normalized)
        return {"event_id": f"event-{len(self.events)}"}


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            payload={},
        )
    )


@pytest.mark.lock
def test_audio_and_mood_handlers_preserve_tenant_and_channel() -> None:
    effects = FakeEffects()

    handle_send_audio(
        {
            "tenant_id": "business-a",
            "user_id": "user-1",
            "path": "https://cdn.example/audio.ogg",
            "channel": "telegram",
        },
        effects,
        _env(),
    )
    handle_log_mood(
        {
            "tenant_id": "business-a",
            "user_id": "user-1",
            "score": 8,
            "channel": "whatsapp",
            "channel_policy": {"fallback_channels": ["sms", "email"]},
        },
        effects,
        _env(),
    )

    audio = effects.calls[0][1]
    mood = effects.calls[1][1]
    assert audio["tenant_id"] == "business-a"
    assert audio["channel"] == "telegram"
    assert mood["tenant_id"] == "business-a"
    assert mood["channel"] == "whatsapp"
    assert mood["channel_policy"] == {
        "fallback_channels": ["sms", "email"]
    }


@pytest.mark.lock
def test_invalid_gift_does_not_grant_entitlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    event_log = FakeEventLog([])
    effects = FakeEffects(event_log)

    result = access.grant_access_effect(
        effects,
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="business-a",
        product_id="product-a",
        user_id="user-1",
        track_event_type="gift_redeemed",
        track_payload={"token": "missing"},
    )

    assert result["ok"] is False
    assert result["reason"] == "not_found"
    assert not any(
        event["event_type"] == "entitlement_granted"
        for event in event_log.events
    )


@pytest.mark.lock
def test_valid_gift_uses_canonical_entitlement_primitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    initial = [
        {
            "event_type": "gift_token_created",
            "payload": {
                "token": "gift-1",
                "created_by": "admin-1",
                "expires_ms": 0,
            },
        }
    ]
    event_log = FakeEventLog(initial)
    effects = FakeEffects(event_log)

    result = access.grant_access_effect(
        effects,
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="business-a",
        product_id="product-a",
        user_id="user-1",
        track_event_type="gift_redeemed",
        track_payload={"token": "gift-1"},
    )

    assert result["ok"] is True
    assert result["entitlement"]["grant_key"] == "gift-1"
    assert [
        event["event_type"]
        for event in event_log.events
    ][-2:] == ["gift_redeemed", "entitlement_granted"]
