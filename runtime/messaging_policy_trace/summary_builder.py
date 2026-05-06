from __future__ import annotations

from runtime.messaging_policy_events.snapshot_builder import MessagingPolicySnapshotBuilder
from runtime.messaging_policy_trace.summary_record import MessagingPolicyTraceSummary


class MessagingPolicyTraceSummaryBuilder:
    def __init__(self, *, snapshot_builder: MessagingPolicySnapshotBuilder | None = None):
        self._snapshot_builder = snapshot_builder or MessagingPolicySnapshotBuilder()

    def build_one(self, records) -> MessagingPolicyTraceSummary | None:
        records = list(records or ())
        if not records:
            return None
        ordered = sorted(records, key=lambda x: (int(getattr(x, 'timestamp_ms', 0) or 0), str(getattr(x, 'event_id', '') or '')))
        first = ordered[0]
        last = ordered[-1]
        snap = self._snapshot_builder.build(ordered)
        return MessagingPolicyTraceSummary(
            tenant_id=first.tenant_id,
            user_id=first.user_id,
            correlation_id=first.correlation_id,
            decision_id=first.decision_id,
            created_at=str(getattr(first, 'created_at', '') or ''),
            updated_at=str(getattr(last, 'created_at', '') or ''),
            attempts_count=int(snap.attempts_count),
            selected_channel=str(snap.last_selected_channel or ''),
            terminal_reason=str(snap.last_terminal_reason or ''),
            delivered=tuple(snap.delivered),
            failed=tuple(snap.failed),
            blocked=tuple(snap.blocked),
            last_plan_channels=tuple(snap.last_plan_channels),
        )
