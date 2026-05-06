from __future__ import annotations

from runtime.messaging_policy_trace.group_bucket import TraceBucket
from runtime.messaging_policy_trace.group_key import build_trace_group_key


def group_records(records) -> tuple[TraceBucket, ...]:
    buckets: dict[tuple[str, str, str], TraceBucket] = {}
    for record in list(records or ()):
        key = build_trace_group_key(
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            correlation_id=record.correlation_id,
        )
        bucket = buckets.get(key)
        if bucket is None:
            bucket = TraceBucket(
                tenant_id=record.tenant_id,
                user_id=record.user_id,
                correlation_id=record.correlation_id,
            )
            buckets[key] = bucket
        bucket.records.append(record)
    return tuple(buckets.values())
