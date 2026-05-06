from __future__ import annotations

from runtime.messaging_policy_readmodel.record_dedupe import dedupe_channels
from runtime.messaging_policy_readmodel.snapshot_record import MessagingPolicySnapshotRecord


def accumulator_to_snapshot(acc) -> MessagingPolicySnapshotRecord:
    return MessagingPolicySnapshotRecord(
        tenant_id=acc.tenant_id,
        user_id=acc.user_id,
        correlation_id=acc.correlation_id,
        delivered=dedupe_channels(acc.delivered),
        failed=dedupe_channels(acc.failed),
        blocked=dedupe_channels(acc.blocked),
        last_plan_channels=tuple(acc.last_plan_channels),
        last_selected_channel=str(acc.last_selected_channel or ''),
        last_terminal_reason=str(acc.last_terminal_reason or ''),
        attempts_count=int(acc.attempts_count),
    )
