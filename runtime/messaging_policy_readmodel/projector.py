from __future__ import annotations

from runtime.messaging_policy_readmodel.projector_rules import apply_record
from runtime.messaging_policy_readmodel.record_to_snapshot import accumulator_to_snapshot
from runtime.messaging_policy_readmodel.state_factory import new_accumulator


class MessagingPolicyProjector:
    def project(self, records):
        records = list(records or [])
        if not records:
            return None
        first = records[0]
        acc = new_accumulator(
            tenant_id=first.tenant_id,
            user_id=first.user_id,
            correlation_id=first.correlation_id,
        )
        for record in records:
            apply_record(acc, record)
        return accumulator_to_snapshot(acc)
