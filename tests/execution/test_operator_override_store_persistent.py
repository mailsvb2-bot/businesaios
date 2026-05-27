from __future__ import annotations

import time
from datetime import timedelta

from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRequest,
    OperatorOverrideResolution,
    OperatorOverrideStatus,
    utc_now,
)
from execution.operator_override_store import PersistentOperatorOverrideStore
from governance.rbac_contract import RoleId


def test_persistent_operator_override_store_persists_consumed_status_across_restart(tmp_path) -> None:
    path = tmp_path / 'operator_overrides.json'
    store = PersistentOperatorOverrideStore(path)
    record = store.create(
        OperatorOverrideRequest(
            override_id='ovr-1',
            tenant_id='tenant-a',
            execution_id='exec-1',
            decision_id='dec-1',
            action_name='send_email',
            requested_by='user-1',
            reason='allow once',
            subject_fingerprint='fp-1',
        )
    )
    approved = store.save(
        record.__class__(
            request=record.request,
            status=OperatorOverrideStatus.APPROVED,
            decision=OperatorOverrideDecision(
                override_id='ovr-1',
                tenant_id='tenant-a',
                actor_id='owner-1',
                role_id=RoleId.OWNER,
                resolution=OperatorOverrideResolution.APPROVE_ONCE,
                note='ok',
            ),
            final_reason='approved',
        )
    )
    consumed = store.save(approved.consume_once(execution_id='exec-1'))
    assert consumed.status is OperatorOverrideStatus.CONSUMED

    reloaded = PersistentOperatorOverrideStore(path)
    fetched = reloaded.get('ovr-1')
    assert fetched is not None
    assert fetched.status is OperatorOverrideStatus.CONSUMED
    assert fetched.consumed_by_execution_id == 'exec-1'
    assert reloaded.list_open(tenant_id='tenant-a') == ()


def test_persistent_operator_override_store_persists_expired_status_on_read(tmp_path) -> None:
    path = tmp_path / 'operator_overrides_expire.json'
    store = PersistentOperatorOverrideStore(path)
    store.create(
        OperatorOverrideRequest(
            override_id='ovr-expired',
            tenant_id='tenant-a',
            execution_id='exec-expired',
            decision_id='dec-expired',
            action_name='send_email',
            requested_by='user-1',
            reason='expires soon',
            subject_fingerprint='fp-expired',
            expires_at=utc_now() + timedelta(milliseconds=1),
        )
    )
    time.sleep(0.01)
    fetched = store.get('ovr-expired')
    assert fetched is not None
    assert fetched.status is OperatorOverrideStatus.EXPIRED

    reloaded = PersistentOperatorOverrideStore(path)
    fetched = reloaded.get('ovr-expired')
    assert fetched is not None
    assert fetched.status is OperatorOverrideStatus.EXPIRED
