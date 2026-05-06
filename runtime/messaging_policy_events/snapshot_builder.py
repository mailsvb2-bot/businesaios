from __future__ import annotations

from runtime.messaging_policy_events.event_types import (
    EVENT_CHANNEL_BLOCKED,
    EVENT_MESSAGE_DELIVERED,
    EVENT_MESSAGE_FAILED,
    EVENT_POLICY_EXECUTION_FINISHED,
    EVENT_POLICY_PLAN_CREATED,
)
from runtime.messaging_policy_events.snapshot_state import MessagingPolicySnapshotState


def _dedupe(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(x) for x in items if str(x).strip()))


class MessagingPolicySnapshotBuilder:
    def build(self, records) -> MessagingPolicySnapshotState:
        delivered: list[str] = []
        failed: list[str] = []
        blocked: list[str] = []
        last_plan_channels: tuple[str, ...] = ()
        last_selected_channel = ''
        last_terminal_reason = ''
        attempts_count = 0
        for record in list(records or ()):
            payload = dict(getattr(record, 'payload', {}) or {})
            channel = str(payload.get('channel') or '')
            if record.event_type == EVENT_MESSAGE_DELIVERED and channel:
                delivered.append(channel)
                attempts_count += 1
            elif record.event_type == EVENT_MESSAGE_FAILED and channel:
                failed.append(channel)
                attempts_count += 1
            elif record.event_type == EVENT_CHANNEL_BLOCKED and channel:
                blocked.append(channel)
            elif record.event_type == EVENT_POLICY_PLAN_CREATED:
                last_plan_channels = tuple(str(x) for x in payload.get('ordered_channels') or ())
            elif record.event_type == EVENT_POLICY_EXECUTION_FINISHED:
                last_selected_channel = str(payload.get('selected_channel') or '')
                last_terminal_reason = str(payload.get('terminal_reason') or '')
                attempts = payload.get('attempts_count')
                if attempts not in (None, ''):
                    attempts_count = max(attempts_count, int(attempts))
        return MessagingPolicySnapshotState(
            delivered=_dedupe(delivered),
            failed=_dedupe(failed),
            blocked=_dedupe(blocked),
            last_plan_channels=last_plan_channels,
            last_selected_channel=last_selected_channel,
            last_terminal_reason=last_terminal_reason,
            attempts_count=int(attempts_count),
        )
