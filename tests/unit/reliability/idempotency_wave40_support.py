from __future__ import annotations

from datetime import UTC, datetime, timedelta

from reliability.idempotency_contract import IdempotencyKey, IdempotencyState

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


def key(name: str = "job-1", scope: str = "scope-a") -> IdempotencyKey:
    return IdempotencyKey("tenant-a", "runtime", "execute", name, scope)


def record_row(
    name: str = "job-1",
    *,
    state: IdempotencyState = IdempotencyState.IN_PROGRESS,
    owner: str = "owner-a",
    lease: datetime | None = NOW + timedelta(seconds=30),
) -> dict[str, object]:
    return {
        "tenant_id": "tenant-a",
        "namespace": "runtime",
        "operation": "execute",
        "key": name,
        "scope_hash": "scope-a",
        "state": state.value,
        "first_seen_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
        "lease_expires_at": None if lease is None else lease.isoformat(),
        "completed_at": (
            NOW.isoformat() if state is IdempotencyState.COMPLETED else None
        ),
        "owner_id": owner,
        "attempt_count": 1,
        "result_ref": "result://1" if state is IdempotencyState.COMPLETED else None,
        "result_digest": "digest" if state is IdempotencyState.COMPLETED else None,
        "failure_reason": "boom" if state is IdempotencyState.FAILED else None,
        "metadata": {"source": "test"},
    }
