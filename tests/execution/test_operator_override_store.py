from __future__ import annotations

from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRequest,
    OperatorOverrideResolution,
    OperatorOverrideStatus,
)
from execution.operator_override_store import InMemoryOperatorOverrideStore
from governance.rbac_contract import RoleId


def test_inmemory_operator_override_store_roundtrip() -> None:
    store = InMemoryOperatorOverrideStore()
    created = store.create(
        OperatorOverrideRequest(
            override_id='ovr-1',
            tenant_id='tenant-a',
            execution_id='exec-1',
            decision_id='dec-1',
            action_name='send_email',
            requested_by='user-1',
            reason='need operator approval',
            subject_fingerprint='fp-1',
        )
    )
    assert created.status is OperatorOverrideStatus.REQUESTED
    fetched = store.get('ovr-1')
    assert fetched is not None
    updated = store.save(
        fetched.__class__(
            request=fetched.request,
            status=OperatorOverrideStatus.APPROVED,
            decision=OperatorOverrideDecision(
                override_id='ovr-1',
                tenant_id='tenant-a',
                actor_id='owner-1',
                role_id=RoleId.OWNER,
                resolution=OperatorOverrideResolution.APPROVE_ONCE,
                note='approved once',
            ),
            final_reason='approved',
        )
    )
    assert updated.status is OperatorOverrideStatus.APPROVED
    assert store.list_open(tenant_id='tenant-a') == ()


from datetime import timedelta
from execution.operator_override_contract import utc_now


def test_inmemory_operator_override_store_expires_stale_request() -> None:
    store = InMemoryOperatorOverrideStore()
    store.create(
        OperatorOverrideRequest(
            override_id='ovr-expired',
            tenant_id='tenant-a',
            execution_id='exec-9',
            decision_id='dec-9',
            action_name='send_email',
            requested_by='user-1',
            reason='expired request',
            subject_fingerprint='fp-expired',
            expires_at=utc_now() + timedelta(milliseconds=1),
        )
    )
    import time
    time.sleep(0.01)
    fetched = store.get('ovr-expired')
    assert fetched is not None
    assert fetched.status is OperatorOverrideStatus.EXPIRED
    assert store.list_open(tenant_id='tenant-a') == ()
