from __future__ import annotations

from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.event_types import (
    EVENT_POLICY_EXECUTION_FINISHED,
    EVENT_POLICY_PLAN_CREATED,
)


def build_policy_plan_created_event(*, msg: OutboundMessage, plan: PolicyPlan):
    return build_event(
        tenant_id=msg.tenant_id,
        user_id=msg.user_id,
        decision_id=msg.decision_id,
        correlation_id=msg.correlation_id,
        event_type=EVENT_POLICY_PLAN_CREATED,
        payload={
            'ordered_channels': list(plan.ordered_channels),
            'reason_codes': list(plan.reason_codes),
            'terminal_reason': str(plan.terminal_reason or ''),
        },
    )


def build_policy_execution_finished_event(
    *,
    msg: OutboundMessage,
    plan: PolicyPlan,
    selected_channel: str,
    terminal_reason: str,
    attempts_count: int,
):
    return build_event(
        tenant_id=msg.tenant_id,
        user_id=msg.user_id,
        decision_id=msg.decision_id,
        correlation_id=msg.correlation_id,
        event_type=EVENT_POLICY_EXECUTION_FINISHED,
        payload={
            'selected_channel': str(selected_channel or ''),
            'terminal_reason': str(terminal_reason or ''),
            'ordered_channels': list(plan.ordered_channels),
            'attempts_count': int(attempts_count),
        },
    )
