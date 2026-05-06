from __future__ import annotations

from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy_events.attempt_event_builder import build_attempt_events
from runtime.messaging_policy_events.policy_plan_event_builder import (
    build_policy_execution_finished_event,
    build_policy_plan_created_event,
)


class MessagingPolicyEventRecorder:
    def __init__(self, *, store):
        self._store = store

    def record_plan(self, *, msg: OutboundMessage, plan: PolicyPlan) -> None:
        self._store.append(build_policy_plan_created_event(msg=msg, plan=plan))

    def record_attempt(self, *, msg: OutboundMessage, ok: bool, meta: dict | None = None) -> None:
        for event in build_attempt_events(msg=msg, ok=ok, meta=meta):
            self._store.append(event)

    def record_finished(
        self,
        *,
        msg: OutboundMessage,
        plan: PolicyPlan,
        selected_channel: str,
        terminal_reason: str,
        attempts_count: int,
    ) -> None:
        self._store.append(
            build_policy_execution_finished_event(
                msg=msg,
                plan=plan,
                selected_channel=selected_channel,
                terminal_reason=terminal_reason,
                attempts_count=attempts_count,
            )
        )
