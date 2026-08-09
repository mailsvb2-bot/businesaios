from __future__ import annotations

from runtime._internal.effect_router import _sanitize_internal_result
from runtime._internal.effect_types import EffectActionType
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy_events.execute_with_events import execute_policy_plan_with_events


def test_attempt_guard_exception_fails_closed_without_policy_events() -> None:
    events: list[str] = []

    class Recorder:
        def record_plan(self, **_kwargs) -> None:
            events.append("plan")

        def record_attempt(self, **_kwargs) -> None:
            events.append("attempt")

        def record_finished(self, **_kwargs) -> None:
            events.append("finished")

    msg = OutboundMessage(
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="tenant-a",
        user_id="user-1",
        channel="telegram",
        text="approved",
    )
    plan = PolicyPlan(
        ordered_channels=("telegram", "email"),
        reason_codes=("approved_delivery_route",),
    )

    def exploding_guard(_msg) -> str:
        raise RuntimeError("settings backend unavailable")

    ok, meta = execute_policy_plan_with_events(
        plan=plan,
        base_message=msg,
        send_once=lambda _msg: (_ for _ in ()).throw(AssertionError("transport must not run")),
        recorder=Recorder(),
        attempt_guard=exploding_guard,
    )

    assert ok is False
    assert meta == {}
    assert events == []


def test_effect_router_strips_transport_guard_details_before_evidence() -> None:
    raw = {
        "ok": False,
        "mode": "blocked",
        "transport_guard_reason": "preference_changed",
        "_transport_guard_debug": "private",
        "delivery_key": "must-not-leak-on-block",
    }

    sanitized = _sanitize_internal_result(EffectActionType.TELEGRAM_SEND_MESSAGE, raw)

    assert sanitized == {"ok": False, "mode": "blocked"}


def test_effect_router_recursively_strips_nested_guard_fields() -> None:
    raw = {
        "ok": True,
        "mode": "direct",
        "data": {
            "safe": "kept",
            "transport_guard_reason": "preference_changed",
            "items": [
                {"external_id": "msg-1", "_transport_guard_debug": "private"},
                {"nested": {"transport_guard_reason": "private", "safe": 7}},
            ],
        },
        "meta": {
            "safe": "value",
            "_transport_guard_trace": "private",
        },
    }

    sanitized = _sanitize_internal_result(EffectActionType.TELEGRAM_SEND_MESSAGE, raw)

    assert sanitized == {
        "ok": True,
        "mode": "direct",
        "data": {
            "safe": "kept",
            "items": [
                {"external_id": "msg-1"},
                {"nested": {"safe": 7}},
            ],
        },
        "meta": {"safe": "value"},
    }


def test_effect_router_sanitizer_does_not_rewrite_normal_provider_result() -> None:
    raw = {"ok": True, "mode": "direct", "external_id": "msg-1"}
    assert _sanitize_internal_result(EffectActionType.TELEGRAM_SEND_MESSAGE, raw) == raw
