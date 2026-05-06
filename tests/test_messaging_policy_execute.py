from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.effects_integration import execute_policy_plan
from runtime.messaging_policy.policy_plan import PolicyPlan


def test_execute_policy_plan_selects_first_success():
    attempts = []

    def send_once(msg):
        attempts.append(msg.channel)
        if msg.channel == "whatsapp":
            return False, {"provider": "whatsapp"}
        if msg.channel == "sms":
            return True, {"provider": "sms"}
        return False, {"provider": msg.channel}

    ok, meta = execute_policy_plan(
        plan=PolicyPlan(
            ordered_channels=("whatsapp", "sms", "email"),
            reason_codes=("candidate_sequence_built",),
            terminal_reason="",
        ),
        base_message=OutboundMessage(
            decision_id="d1",
            correlation_id="c1",
            tenant_id="t1",
            user_id="u1",
            channel="telegram",
            text="hello",
        ),
        send_once=send_once,
    )

    assert ok is True
    assert attempts == ["whatsapp", "sms"]
    assert meta["policy"]["selected_channel"] == "sms"


def test_execute_policy_plan_returns_terminal_if_no_channel():
    ok, meta = execute_policy_plan(
        plan=PolicyPlan(
            ordered_channels=(),
            reason_codes=("already_delivered",),
            terminal_reason="already_delivered",
        ),
        base_message=OutboundMessage(
            decision_id="d1",
            correlation_id="c1",
            tenant_id="t1",
            user_id="u1",
            channel="telegram",
            text="hello",
        ),
        send_once=lambda msg: (True, {}),
    )

    assert ok is False
    assert meta["policy"]["terminal_reason"] == "already_delivered"
