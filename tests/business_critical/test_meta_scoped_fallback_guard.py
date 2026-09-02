from types import SimpleNamespace

import pytest

import runtime._internal.effects_actions.telegram.messaging_parts.policy as policy_module
from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan


def _message(channel: str) -> OutboundMessage:
    return OutboundMessage(
        decision_id="decision-meta-fallback",
        correlation_id="correlation-meta-fallback",
        tenant_id="tenant-a",
        business_id="business-a",
        user_id="source-channel-user-id",
        channel=channel,
        text="hello",
    )


@pytest.mark.lock
@pytest.mark.parametrize("source,target", (("whatsapp", "instagram"), ("slack", "messenger")))
def test_policy_drops_meta_fallback_without_channel_scoped_recipient(monkeypatch, source, target):
    runtime = SimpleNamespace(settings_gateway=None)
    monkeypatch.setattr(
        policy_module,
        "load_channel_preference",
        lambda **_kwargs: ChannelPreference(primary=source, enabled=(source, target, "email")),
    )
    monkeypatch.setattr(
        policy_module.MessagingPolicyResolver,
        "resolve",
        lambda _self, _request: PolicyPlan(
            ordered_channels=(source, target, "email"),
            reason_codes=("fallback",),
            terminal_reason="",
        ),
    )
    monkeypatch.setattr(
        policy_module,
        "_apply_capability_routing",
        lambda _self, *, ordered_channels, disciplined_policy: PolicyPlan(
            ordered_channels=tuple(ordered_channels),
            reason_codes=("capability_route_applied",),
            terminal_reason="",
        ),
    )
    monkeypatch.setattr(policy_module, "build_policy_event_recorder_from_runtime", lambda _runtime: None)
    monkeypatch.setattr(policy_module, "_with_health_feedback", lambda _runtime, *, send_once: send_once)
    attempts = []

    def send_once(msg):
        attempts.append(msg.channel)
        return (False, {"reason": "primary_failed"}) if msg.channel == source else (True, {"external_id": "email-1"})

    ok, meta = policy_module.execute_with_policy(
        runtime,
        msg=_message(source),
        channel_policy={"fallback_channels": [target, "email"]},
        send_once=send_once,
    )

    assert ok is True
    assert attempts == [source, "email"]
    assert target not in meta["policy"]["ordered_channels"]
    assert "scoped_recipient_fallback_blocked" in meta["policy"]["reason_codes"]


@pytest.mark.lock
@pytest.mark.parametrize("channel", ("instagram", "messenger"))
def test_policy_keeps_direct_meta_channel(monkeypatch, channel):
    runtime = SimpleNamespace(settings_gateway=None)
    monkeypatch.setattr(
        policy_module,
        "load_channel_preference",
        lambda **_kwargs: ChannelPreference(primary=channel, enabled=(channel, "email")),
    )
    monkeypatch.setattr(
        policy_module.MessagingPolicyResolver,
        "resolve",
        lambda _self, _request: PolicyPlan(
            ordered_channels=(channel, "email"),
            reason_codes=("candidate_sequence_built",),
            terminal_reason="",
        ),
    )
    monkeypatch.setattr(
        policy_module,
        "_apply_capability_routing",
        lambda _self, *, ordered_channels, disciplined_policy: PolicyPlan(
            ordered_channels=tuple(ordered_channels),
            reason_codes=("capability_route_applied",),
            terminal_reason="",
        ),
    )
    monkeypatch.setattr(policy_module, "build_policy_event_recorder_from_runtime", lambda _runtime: None)
    monkeypatch.setattr(policy_module, "_with_health_feedback", lambda _runtime, *, send_once: send_once)
    attempts = []

    def send_once(msg):
        attempts.append(msg.channel)
        return True, {"external_id": "meta-receipt-1"}

    ok, meta = policy_module.execute_with_policy(
        runtime,
        msg=_message(channel),
        channel_policy={"fallback_channels": ["email"]},
        send_once=send_once,
    )

    assert ok is True
    assert attempts == [channel]
    assert meta["policy"]["selected_channel"] == channel
    assert "scoped_recipient_fallback_blocked" not in meta["policy"]["reason_codes"]
