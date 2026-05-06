from __future__ import annotations

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.event_types import (
    EVENT_CHANNEL_BLOCKED,
    EVENT_MESSAGE_ATTEMPTED,
    EVENT_MESSAGE_DELIVERED,
    EVENT_MESSAGE_FAILED,
)


def build_attempt_events(
    *,
    msg: OutboundMessage,
    ok: bool,
    meta: dict | None = None,
) -> list:
    payload = {
        'channel': normalize_channel(msg.channel),
        'ok': bool(ok),
        'external_id': str((meta or {}).get('external_id') or ''),
        'mode': str((meta or {}).get('mode') or ''),
        'meta': dict(meta or {}),
    }

    events = [
        build_event(
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            decision_id=msg.decision_id,
            correlation_id=msg.correlation_id,
            event_type=EVENT_MESSAGE_ATTEMPTED,
            payload=payload,
        )
    ]

    if bool(ok):
        events.append(
            build_event(
                tenant_id=msg.tenant_id,
                user_id=msg.user_id,
                decision_id=msg.decision_id,
                correlation_id=msg.correlation_id,
                event_type=EVENT_MESSAGE_DELIVERED,
                payload=payload,
            )
        )
    else:
        events.append(
            build_event(
                tenant_id=msg.tenant_id,
                user_id=msg.user_id,
                decision_id=msg.decision_id,
                correlation_id=msg.correlation_id,
                event_type=EVENT_MESSAGE_FAILED,
                payload=payload,
            )
        )
        reason = str((meta or {}).get('reason') or '')
        if reason == 'blocked':
            events.append(
                build_event(
                    tenant_id=msg.tenant_id,
                    user_id=msg.user_id,
                    decision_id=msg.decision_id,
                    correlation_id=msg.correlation_id,
                    event_type=EVENT_CHANNEL_BLOCKED,
                    payload=payload,
                )
            )
    return events
