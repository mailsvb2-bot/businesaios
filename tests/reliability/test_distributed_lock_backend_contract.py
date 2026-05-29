from __future__ import annotations

from datetime import datetime, timezone, UTC

import pytest

from reliability.distributed_lock import LockLease
from reliability.distributed_lock_backend import (
    LockBackendRecord,
    build_expires_at,
    datetime_to_epoch_ms,
    ensure_aware,
    epoch_ms_to_datetime,
    normalize_lock_inputs,
    safe_sql_identifier,
)

UTC = UTC


def _t(second: int = 0) -> datetime:
    return datetime(2026, 1, 1, 0, 0, second, tzinfo=UTC)


def test_build_expires_at() -> None:
    assert build_expires_at(now=_t(), ttl_seconds=30) == _t(30)


def test_epoch_ms_roundtrip_for_second_aligned_timestamp() -> None:
    moment = _t(17)
    assert epoch_ms_to_datetime(datetime_to_epoch_ms(moment)) == moment


def test_ensure_aware_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        ensure_aware(datetime(2026, 1, 1, 0, 0, 0))


def test_normalize_lock_inputs() -> None:
    tid, res, owner, ttl, now = normalize_lock_inputs(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=15, now=_t())
    assert tid == 'tenant-a'
    assert res == 'scheduler'
    assert owner == 'node-1'
    assert ttl == 15
    assert now == _t()


def test_lock_backend_record_roundtrip() -> None:
    record = LockBackendRecord(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', fencing_token=1, acquired_at=_t(), expires_at=_t(30))
    lease = record.to_lease()
    assert isinstance(lease, LockLease)
    assert LockBackendRecord.from_lease(lease) == record


@pytest.mark.parametrize(('value', 'ok'), [('reliability', True), ('reliability_lock', True), ('a1_b2_c3', True), ('1bad', False), ('bad-name', False), ('bad.name', False), ('bad name', False), ('', False)])
def test_safe_sql_identifier(value: str, ok: bool) -> None:
    if ok:
        assert safe_sql_identifier(value) == value
    else:
        with pytest.raises(ValueError):
            safe_sql_identifier(value)
