from __future__ import annotations

import pytest

import runtime.messaging.bridge as bridge_module
from runtime.messaging.bridge import MultiChannelEffectsBridge
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy_events.execute_with_events import execute_policy_plan_with_events


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.messages = []

    def send(self, msg):
        self.messages.append(msg)
        return DeliveryResult(False, msg.channel, "blocked", "", {"reason": "test"})


def _message(*, channel: str, user_id: str, track_payload: dict | None = None) -> OutboundMessage:
    return OutboundMessage(
        decision_id="dec-1",
        correlation_id="corr-1",
        tenant_id="business-a",
        user_id=user_id,
        channel=channel,
        text="hello",
        track_payload=track_payload,
    )


@pytest.mark.lock
@pytest.mark.parametrize(
    "channel,user_id,recipient_key",
    (("vk", "42", "peer_id"), ("max", "99", "chat_id"), ("slack", "C123", "channel_id"), ("discord", "123", "channel_id")),
)
def test_shared_effect_bridge_binds_native_context_for_direct_and_fallback_sends(monkeypatch, channel, user_id, recipient_key):
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(bridge_module, "build_multichannel_dispatcher", lambda: dispatcher)
    bridge = MultiChannelEffectsBridge()

    bridge.send(_message(channel=channel, user_id=user_id, track_payload={"tenant_id": "business-a"}))

    native = dispatcher.messages[0].track_payload["_provider_native"]
    assert native["business_id"] == "business-a"
    assert native[recipient_key] == user_id


@pytest.mark.lock
def test_shared_effect_bridge_preserves_explicit_native_approval_and_recipient(monkeypatch):
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(bridge_module, "build_multichannel_dispatcher", lambda: dispatcher)
    bridge = MultiChannelEffectsBridge()
    original = {"business_id": "business-explicit", "approval_id": "ap-1", "channel_id": "C999"}

    bridge.send(_message(channel="slack", user_id="C123", track_payload={"_provider_native": original}))

    native = dispatcher.messages[0].track_payload["_provider_native"]
    assert native == original


@pytest.mark.lock
def test_shared_effect_bridge_does_not_add_native_context_to_generic_channel(monkeypatch):
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(bridge_module, "build_multichannel_dispatcher", lambda: dispatcher)
    bridge = MultiChannelEffectsBridge()

    bridge.send(_message(channel="whatsapp", user_id="recipient-1"))

    assert dispatcher.messages[0].track_payload is None


@pytest.mark.lock
def test_shared_effect_bridge_preserves_unknown_channel_missing_adapter_contract(monkeypatch):
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(bridge_module, "build_multichannel_dispatcher", lambda: dispatcher)
    bridge = MultiChannelEffectsBridge()

    bridge.send(_message(channel="unknown-channel", user_id="recipient-1"))

    assert dispatcher.messages[0].channel == "unknown-channel"
    assert dispatcher.messages[0].track_payload is None


@pytest.mark.lock
def test_policy_fallback_binds_native_context_after_final_channel_selection(monkeypatch):
    class _FallbackDispatcher(_RecordingDispatcher):
        def send(self, msg):
            self.messages.append(msg)
            if msg.channel == "whatsapp":
                return DeliveryResult(False, msg.channel, "failed", "", {"reason": "test_primary_failed"})
            return DeliveryResult(True, msg.channel, "accepted", "provider-receipt", {"accepted": True})

    dispatcher = _FallbackDispatcher()
    monkeypatch.setattr(bridge_module, "build_multichannel_dispatcher", lambda: dispatcher)
    bridge = MultiChannelEffectsBridge()
    base = _message(channel="whatsapp", user_id="C123", track_payload={"tenant_id": "business-a"})

    def _send_once(msg):
        result = bridge.send(msg)
        return result.ok, {"mode": result.mode, "channel": result.channel, **dict(result.detail or {})}

    ok, meta = execute_policy_plan_with_events(
        plan=PolicyPlan(ordered_channels=("whatsapp", "slack"), reason_codes=("fallback",), terminal_reason=""),
        base_message=base,
        send_once=_send_once,
    )

    assert ok is True
    assert meta["policy"]["selected_channel"] == "slack"
    assert dispatcher.messages[0].track_payload == {"tenant_id": "business-a"}
    native = dispatcher.messages[1].track_payload["_provider_native"]
    assert native == {"provider_key": "slack_messaging", "business_id": "business-a", "channel_id": "C123"}


@pytest.mark.lock
def test_policy_fallback_rebinds_shared_channel_id_when_native_provider_changes(monkeypatch):
    class _FallbackDispatcher(_RecordingDispatcher):
        def send(self, msg):
            self.messages.append(msg)
            if msg.channel == "slack":
                return DeliveryResult(False, msg.channel, "failed", "", {"reason": "test_primary_failed"})
            return DeliveryResult(True, msg.channel, "accepted", "provider-receipt", {"accepted": True})

    dispatcher = _FallbackDispatcher()
    monkeypatch.setattr(bridge_module, "build_multichannel_dispatcher", lambda: dispatcher)
    bridge = MultiChannelEffectsBridge()
    base = _message(
        channel="slack",
        user_id="123",
        track_payload={
            "tenant_id": "business-a",
            "_provider_native": {
                "provider_key": "slack_messaging",
                "business_id": "business-a",
                "approval_id": "ap-slack",
                "channel_id": "C999",
            },
        },
    )

    def _send_once(msg):
        result = bridge.send(msg)
        return result.ok, {"mode": result.mode, "channel": result.channel, **dict(result.detail or {})}

    ok, meta = execute_policy_plan_with_events(
        plan=PolicyPlan(ordered_channels=("slack", "discord"), reason_codes=("fallback",), terminal_reason=""),
        base_message=base,
        send_once=_send_once,
    )

    assert ok is True
    assert meta["policy"]["selected_channel"] == "discord"
    slack_native = dispatcher.messages[0].track_payload["_provider_native"]
    assert slack_native["provider_key"] == "slack_messaging"
    assert slack_native["channel_id"] == "C999"
    assert slack_native["approval_id"] == "ap-slack"
    discord_native = dispatcher.messages[1].track_payload["_provider_native"]
    assert discord_native == {
        "provider_key": "discord_messaging",
        "business_id": "business-a",
        "channel_id": "123",
    }
