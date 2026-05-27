from __future__ import annotations

import time
import uuid

from runtime.messaging_policy_events.event_record import MessagingPolicyEventRecord
from runtime.messaging_policy_trace.iso_time import safe_parse_iso_to_epoch_ms
from runtime.tenancy import normalize_tenant_scope


def build_event(
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    event_type: str,
    payload: dict | None = None,
    source: str = 'messaging_policy',
    timestamp_ms: int | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> MessagingPolicyEventRecord:
    ts = int(timestamp_ms or 0)
    if ts <= 0 and str(created_at or '').strip():
        ts = safe_parse_iso_to_epoch_ms(str(created_at))
    if ts <= 0:
        ts = int(time.time() * 1000)
    return MessagingPolicyEventRecord(
        tenant_id=normalize_tenant_scope(tenant_id, allow_unknown=True),
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        event_type=str(event_type),
        payload=dict(payload or {}),
        source=str(source or 'messaging_policy'),
        timestamp_ms=ts,
        event_id=str(event_id or uuid.uuid4()),
    )
