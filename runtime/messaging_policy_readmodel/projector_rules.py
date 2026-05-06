from __future__ import annotations

from runtime.messaging_policy_events.event_types import (
    EVENT_CHANNEL_BLOCKED,
    EVENT_MESSAGE_DELIVERED,
    EVENT_MESSAGE_FAILED,
    EVENT_POLICY_EXECUTION_FINISHED,
    EVENT_POLICY_PLAN_CREATED,
)


def apply_record(acc, record) -> None:
    payload = dict(record.payload or {})
    channel = str(payload.get('channel') or '')

    if record.event_type == EVENT_MESSAGE_DELIVERED and channel:
        acc.delivered.append(channel)
        acc.attempts_count += 1
        return

    if record.event_type == EVENT_MESSAGE_FAILED and channel:
        acc.failed.append(channel)
        acc.attempts_count += 1
        return

    if record.event_type == EVENT_CHANNEL_BLOCKED and channel:
        acc.blocked.append(channel)
        return

    if record.event_type == EVENT_POLICY_PLAN_CREATED:
        acc.last_plan_channels = tuple(str(x) for x in payload.get('ordered_channels') or ())
        return

    if record.event_type == EVENT_POLICY_EXECUTION_FINISHED:
        acc.last_selected_channel = str(payload.get('selected_channel') or '')
        acc.last_terminal_reason = str(payload.get('terminal_reason') or '')
        attempts = payload.get('attempts_count')
        if attempts not in (None, ''):
            acc.attempts_count = max(acc.attempts_count, int(attempts))
