from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tenancy.tenant_admission_coordinator import LeaseStoreAdmissionBackend
from tenancy.tenant_backend_clock_policy import TenantBackendClockPolicy
from tenancy.tenant_metrics_event_log import TenantMetricsEventLog
from tenancy.tenant_metrics_store import InMemoryTenantMetricsStore
from tenancy.tenant_runtime_lease_recovery import TenantRuntimeLeaseRecoveryService, TenantRuntimeRecoveryPlan
from tenancy.tenant_runtime_lease_store import InMemoryTenantRuntimeLeaseStore
from tenancy.tenant_runtime_reconciliation import TenantRuntimeReconciler
from tenancy.tenant_schema_version_guard import TenantSchemaVersionExpectation
from tenancy.tenant_startup_selfcheck import TenantStartupSelfcheck


@dataclass(frozen=True)
class StaticSchemaBackend:
    version: int

    def schema_version(self) -> int:
        return int(self.version)


@dataclass(frozen=True)
class StaticClockReader:
    now: datetime

    def read_backend_clock(self) -> datetime:
        return self.now


def test_crash_recovery_reacquires_desired_runs() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    backend = LeaseStoreAdmissionBackend(lease_store=store)
    reconciler = TenantRuntimeReconciler(lease_store=store, admission_backend=backend)
    recovery = TenantRuntimeLeaseRecoveryService(lease_store=store, reconciler=reconciler)
    plan = TenantRuntimeRecoveryPlan(
        tenant_id='tenant-a',
        limit=3,
        ttl_seconds=60,
        owner_id='recover-worker',
        labels={'source': 'recovery'},
    )
    result = recovery.recover(plan=plan, desired_runs=('run-1', 'run-2', 'run-1'))
    assert result.reacquired_runs == ('run-1', 'run-2')
    assert result.denied_runs == ()
    assert len(store.list_active(tenant_id='tenant-a')) == 2


def test_startup_selfcheck_and_metrics_event_log() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    backend = LeaseStoreAdmissionBackend(lease_store=store)
    metrics = InMemoryTenantMetricsStore()
    log = TenantMetricsEventLog(store=metrics)
    log.emit_counter(tenant_id='tenant-a', event_name='startup_ok', labels={'component': 'tenant_ops'})
    reader = StaticClockReader(now=datetime.now(timezone.utc))
    selfcheck = TenantStartupSelfcheck(lease_store=store, admission_backend=backend, clock_policy=TenantBackendClockPolicy(skew_tolerance_seconds=5))
    result = selfcheck.run(
        tenant_id='tenant-a',
        schema_backends=((StaticSchemaBackend(version=3), TenantSchemaVersionExpectation(component='tenant_lease_store', minimum_version=1, maximum_version=5)),),
        clock_readers=(reader,),
        limit=3,
    )
    assert result.ok is True
    aggregate = metrics.aggregate(tenant_id='tenant-a', metric_name='tenant_runtime.startup_ok')
    assert aggregate is not None
    assert aggregate.sample_count == 1


def test_selfcheck_detects_parity_mismatch() -> None:
    runtime_store = InMemoryTenantRuntimeLeaseStore()
    admission_store = InMemoryTenantRuntimeLeaseStore()
    now = datetime.now(timezone.utc)
    runtime_store.acquire(tenant_id='tenant-a', run_id='run-1', owner_id='worker-a', limit=3, ttl_seconds=60, now=now)
    admission_store.acquire(tenant_id='tenant-a', run_id='run-1', owner_id='worker-b', limit=3, ttl_seconds=60, now=now)
    backend = LeaseStoreAdmissionBackend(lease_store=admission_store)
    selfcheck = TenantStartupSelfcheck(lease_store=runtime_store, admission_backend=backend)
    try:
        selfcheck.run(tenant_id='tenant-a', limit=3)
    except RuntimeError as exc:
        assert 'owner_mismatch' in str(exc)
    else:
        raise AssertionError('expected selfcheck parity mismatch failure')
