from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_admission_contract import TenantAdmissionBackend
from tenancy.tenant_backend_clock_policy import (
    ClockObservation,
    TenantBackendClockPolicy,
    TenantBackendClockReader,
    ensure_aware,
    utc_now,
)
from tenancy.tenant_backend_timeout_policy import TenantBackendTimeoutPolicy
from tenancy.tenant_runtime_invariant_checks import TenantRuntimeInvariantChecks
from tenancy.tenant_runtime_lease_store import TenantRuntimeLeaseStore
from tenancy.tenant_schema_version_guard import TenantSchemaVersionBackend, TenantSchemaVersionExpectation, TenantSchemaVersionGuard


CANON_TENANT_STARTUP_SELFCHECK = True


@dataclass(frozen=True)
class TenantStartupSelfcheckResult:
    tenant_id: str
    ok: bool
    checks: tuple[str, ...]


class TenantStartupSelfcheck:
    def __init__(
        self,
        *,
        lease_store: TenantRuntimeLeaseStore,
        admission_backend: TenantAdmissionBackend,
        clock_policy: TenantBackendClockPolicy | None = None,
        timeout_policy: TenantBackendTimeoutPolicy | None = None,
        invariant_checks: TenantRuntimeInvariantChecks | None = None,
        schema_guard: TenantSchemaVersionGuard | None = None,
    ) -> None:
        self._lease_store = lease_store
        self._admission_backend = admission_backend
        self._clock_policy = clock_policy or TenantBackendClockPolicy()
        self._timeout_policy = timeout_policy or TenantBackendTimeoutPolicy()
        self._checks = invariant_checks or TenantRuntimeInvariantChecks()
        self._schema_guard = schema_guard or TenantSchemaVersionGuard()

    def run(
        self,
        *,
        tenant_id: str,
        schema_backends: Sequence[tuple[TenantSchemaVersionBackend, TenantSchemaVersionExpectation]] = (),
        clock_readers: Sequence[TenantBackendClockReader] = (),
        limit: int | None = None,
        now: datetime | None = None,
    ) -> TenantStartupSelfcheckResult:
        tid = require_tenant_id(tenant_id)
        started_at = ensure_aware(now or utc_now())
        deadline = self._timeout_policy.deadline(operation='selfcheck', now=started_at)
        checks: list[str] = []

        for backend, expectation in schema_backends:
            self._timeout_policy.assert_not_expired(operation='selfcheck', deadline=deadline, now=utc_now())
            version = self._schema_guard.assert_compatible(backend=backend, expectation=expectation)
            checks.append(f'schema:{expectation.component}:{version}')

        for reader in clock_readers:
            observed_at = utc_now()
            self._timeout_policy.assert_not_expired(operation='selfcheck', deadline=deadline, now=observed_at)
            observed = ClockObservation(observed_at=observed_at, backend_now=reader.read_backend_clock())
            self._clock_policy.assert_backend_clock(observation=observed)
            checks.append('clock:ok')

        moment = utc_now()
        self._timeout_policy.assert_not_expired(operation='selfcheck', deadline=deadline, now=moment)
        runtime_leases = self._lease_store.list_active(tenant_id=tid, now=moment)
        admission_leases = self._admission_backend.list_active(tenant_id=tid)

        runtime_report = self._checks.evaluate_runtime_leases(tenant_id=tid, leases=runtime_leases, limit=limit, now=moment)
        admission_report = self._checks.evaluate_admission_leases(tenant_id=tid, admissions=admission_leases, limit=limit, now=moment)
        parity_report = self._checks.evaluate_semantic_parity(tenant_id=tid, leases=runtime_leases, admissions=admission_leases, now=moment)

        combined = (*runtime_report.violations, *admission_report.violations, *parity_report.violations)
        if combined:
            codes = ','.join(sorted({item.code for item in combined}))
            raise RuntimeError(f'tenant startup selfcheck failed: tenant={tid} codes={codes}')

        checks.append('runtime_invariants:ok')
        checks.append('admission_invariants:ok')
        checks.append('semantic_parity:ok')
        return TenantStartupSelfcheckResult(tenant_id=tid, ok=True, checks=tuple(checks))


__all__ = [
    'CANON_TENANT_STARTUP_SELFCHECK',
    'TenantStartupSelfcheck',
    'TenantStartupSelfcheckResult',
]
