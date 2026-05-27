from runtime._internal.effects_actions.telegram.messaging_parts.policy import execute_with_policy
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_capability import ChannelHealth, ChannelHealthRegistry


class _Self:
    def __init__(self):
        self.settings_gateway = _GW()
        self.messaging_channel_health_registry = ChannelHealthRegistry(items=(
            ChannelHealth(channel="telegram", healthy=False, health_score=0.0, reason="down"),
            ChannelHealth(channel="email", healthy=True, health_score=1.0),
        ))
        self.event_log = None


class _GW:
    def get_value(self, *, tenant_id: str, key: str):
        return {
            "primary": "telegram",
            "enabled": ["telegram", "email", "sms"],
            "verified": ["telegram", "email", "sms"],
        }


class _RecorderSelf(_Self):
    pass


def test_execute_with_policy_applies_capability_and_health_filters():
    sent = []

    def send_once(msg):
        sent.append(msg.channel)
        return True, {"external_id": "x", "mode": "delivered"}

    ok, meta = execute_with_policy(
        _RecorderSelf(),
        msg=OutboundMessage(
            decision_id="d1",
            correlation_id="c1",
            tenant_id="t1",
            user_id="u1",
            channel="telegram",
            text="hello",
            payload={"execution_entrypoint": "runtime.execution.decision_execution_service"},
        ),
        channel_policy={
            "fallback_channels": ["email", "sms"],
            "required_capabilities": {"subject_line": True},
        },
        send_once=send_once,
    )

    assert ok is True
    assert sent == ["email"]
    assert meta["policy"]["selected_channel"] == "email"
