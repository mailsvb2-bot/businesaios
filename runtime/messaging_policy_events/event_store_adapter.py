from __future__ import annotations

from typing import Any

from runtime.messaging_policy_events.event_record import MessagingPolicyEventRecord
from runtime.messaging_policy_events.event_types import MESSAGING_POLICY_EVENT_TYPES
from runtime.tenancy import normalize_tenant_scope


class EventLogMessagingPolicyEventStore:
    """Adapter over the canonical tenant-scoped EventLog.

    Design rules:
    - writes go through EventLog.emit only
    - reads/searches use the same canonical event stream
    - no secondary messaging-only event store is created
    """

    def __init__(self, *, event_log: Any):
        self._event_log = event_log

    def append(self, record: MessagingPolicyEventRecord) -> None:
        tenant_scope = normalize_tenant_scope(record.tenant_id, allow_unknown=True)
        self._event_log.emit(
            event_type=record.event_type,
            source=record.source,
            user_id=str(record.user_id),
            decision_id=str(record.decision_id),
            correlation_id=str(record.correlation_id),
            timestamp_ms=int(record.timestamp_ms or 0),
            event_id=(str(record.event_id) if str(record.event_id or '').strip() else None),
            payload={
                'tenant_id': tenant_scope,
                **dict(record.payload or {}),
            },
        )

    def read(self, *, tenant_id: str, user_id: str, correlation_id: str) -> list[MessagingPolicyEventRecord]:
        wanted_tenant = normalize_tenant_scope(tenant_id, allow_unknown=True)
        wanted_user = str(user_id)
        wanted_correlation = str(correlation_id)
        out: list[MessagingPolicyEventRecord] = []
        for record in self.iter_events():
            if str(record.tenant_id) != wanted_tenant:
                continue
            if str(record.user_id) != wanted_user:
                continue
            if str(record.correlation_id) != wanted_correlation:
                continue
            out.append(record)
        return out

    def iter_events(self):
        out: list[MessagingPolicyEventRecord] = []
        if self._event_log is None or not hasattr(self._event_log, 'iter_events'):
            return out
        for raw in list(self._event_log.iter_events()):
            event_type = str(raw.get('event_type') or raw.get('type') or '')
            if event_type not in MESSAGING_POLICY_EVENT_TYPES:
                continue
            payload = dict(raw.get('payload') or {})
            out.append(
                MessagingPolicyEventRecord(
                    tenant_id=normalize_tenant_scope(payload.get('tenant_id') or raw.get('tenant_id') or '', allow_unknown=True),
                    user_id=str(raw.get('user_id') or ''),
                    decision_id=str(raw.get('decision_id') or ''),
                    correlation_id=str(raw.get('correlation_id') or ''),
                    event_type=event_type,
                    payload=payload,
                    source=str(raw.get('source') or 'messaging_policy'),
                    timestamp_ms=int(raw.get('timestamp_ms') or 0),
                    event_id=str(raw.get('event_id') or ''),
                )
            )
        out.sort(key=lambda item: (int(item.timestamp_ms or 0), str(item.event_id or '')))
        return out
