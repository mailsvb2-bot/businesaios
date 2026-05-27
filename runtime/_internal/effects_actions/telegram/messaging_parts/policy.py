from __future__ import annotations

from runtime.messaging_capability import (
    MessagingCapabilityRouter,
    parse_capability_requirement,
    resolve_capability_telemetry_updater,
    resolve_channel_health_registry,
)
from runtime.messaging_policy.discipline import (
    MessagingPolicyDisciplineViolation,
    ensure_policy_input_disciplined,
    ensure_policy_plan_disciplined,
)
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy.policy_request import PolicyRequest
from runtime.messaging_policy.read_models import parse_delivery_snapshot, parse_unanswered_snapshot
from runtime.messaging_policy.resolver import MessagingPolicyResolver
from runtime.messaging_policy_events.execute_with_events import execute_policy_plan_with_events
from runtime.messaging_policy_events.runtime_bridge import build_policy_event_recorder_from_runtime
from runtime.messaging_preferences.load_preference import load_channel_preference


def _apply_capability_routing(self, *, ordered_channels: tuple[str, ...], disciplined_policy: dict) -> PolicyPlan:
    requirement = parse_capability_requirement(disciplined_policy.get("required_capabilities"))
    router = MessagingCapabilityRouter(
        health_registry=resolve_channel_health_registry(self),
    )
    routed = router.route(ordered_channels=ordered_channels, requirement=requirement)
    if routed.ordered_channels:
        return PolicyPlan(
            ordered_channels=routed.ordered_channels,
            reason_codes=tuple(dict.fromkeys(tuple(routed.reason_codes) + ("capability_route_applied",))),
            terminal_reason="",
        )
    return PolicyPlan(
        ordered_channels=(),
        reason_codes=tuple(dict.fromkeys(tuple(routed.reason_codes) + ("capability_route_applied",))),
        terminal_reason="no_eligible_channel_after_capability_health_filter",
    )


def _with_health_feedback(self, *, send_once):
    updater = resolve_capability_telemetry_updater(self)

    def _observed(selected_msg):
        ok, meta = send_once(selected_msg)
        updater.record_delivery_outcome(
            channel=str(selected_msg.channel),
            ok=bool(ok),
            meta=dict(meta or {}),
        )
        return ok, meta

    return _observed


def execute_with_policy(self, *, msg, channel_policy: dict, send_once):
    disciplined_policy = ensure_policy_input_disciplined(channel_policy)
    settings_gateway = getattr(self, "settings_gateway", None)
    preference = load_channel_preference(
        settings_gateway=settings_gateway,
        tenant_id=msg.tenant_id,
    )
    resolver = MessagingPolicyResolver()
    plan = ensure_policy_plan_disciplined(
        resolver.resolve(
            PolicyRequest(
                preference=preference,
                preferred_channel=msg.channel,
                fallback_channels=tuple(disciplined_policy.get("fallback_channels") or ()),
                verified_only=bool(disciplined_policy.get("verified_only", False)),
                critical=bool(msg.critical),
                attempt_index=int(disciplined_policy.get("attempt_index") or 0),
                unanswered_threshold_s=int(disciplined_policy.get("unanswered_threshold_s") or 0),
                delivery_snapshot=parse_delivery_snapshot(disciplined_policy.get("delivery_snapshot")),
                unanswered_snapshot=parse_unanswered_snapshot(disciplined_policy.get("unanswered_snapshot")),
            )
        )
    )
    plan = ensure_policy_plan_disciplined(
        _apply_capability_routing(self, ordered_channels=plan.ordered_channels, disciplined_policy=disciplined_policy)
    )
    recorder = build_policy_event_recorder_from_runtime(self)
    return execute_policy_plan_with_events(
        plan=plan,
        base_message=msg,
        send_once=_with_health_feedback(self, send_once=send_once),
        recorder=recorder,
    )


def execute_delivery_path(self, *, msg, channel_policy, send_once):
    if isinstance(channel_policy, dict) and channel_policy:
        try:
            return execute_with_policy(self, msg=msg, channel_policy=channel_policy, send_once=send_once)
        except MessagingPolicyDisciplineViolation as exc:
            return False, {"policy": {"ordered_channels": [], "reason_codes": ["discipline_violation"], "terminal_reason": "discipline_violation", "attempts": []}, "error": exc.__class__.__name__}
    return send_once(msg)
