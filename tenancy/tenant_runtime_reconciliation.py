from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_admission_contract import TenantAdmissionBackend
from tenancy.tenant_backend_clock_policy import ensure_aware, utc_now
from tenancy.tenant_runtime_invariant_checks import TenantRuntimeInvariantChecks
from tenancy.tenant_runtime_lease_store import TenantRuntimeLeaseStore


CANON_TENANT_RUNTIME_RECONCILIATION = True


@dataclass(frozen=True)
class TenantRuntimeReconciliationResult:
    tenant_id: str
    released_runtime_runs: tuple[str, ...]
    released_admission_runs: tuple[str, ...]
    report_ok: bool
    violation_codes: tuple[str, ...]


class TenantRuntimeReconciler:
    def __init__(
        self,
        *,
        lease_store: TenantRuntimeLeaseStore,
        admission_backend: TenantAdmissionBackend,
        invariant_checks: TenantRuntimeInvariantChecks | None = None,
    ) -> None:
        self._lease_store = lease_store
        self._admission_backend = admission_backend
        self._checks = invariant_checks or TenantRuntimeInvariantChecks()

    def reconcile(
        self,
        *,
        tenant_id: str,
        limit: int | None = None,
        now: datetime | None = None,
    ) -> TenantRuntimeReconciliationResult:
        tid = require_tenant_id(tenant_id)
        moment = ensure_aware(now or utc_now())
        runtime_leases = self._lease_store.list_active(tenant_id=tid, now=moment)
        admission_leases = self._admission_backend.list_active(tenant_id=tid)
        runtime_map = {item.run_id: item for item in runtime_leases}
        admission_map = {item.run_id: item for item in admission_leases}
        released_runtime: set[str] = set()
        released_admission: set[str] = set()

        for run_id, lease in admission_map.items():
            runtime = runtime_map.get(run_id)
            if runtime is None:
                if self._admission_backend.release(tenant_id=tid, run_id=run_id, owner_id=lease.owner_id):
                    released_admission.add(run_id)
                continue
            if runtime.owner_id != lease.owner_id or int(runtime.fencing_token) != int(lease.fencing_token):
                if self._admission_backend.release(tenant_id=tid, run_id=run_id, owner_id=lease.owner_id):
                    released_admission.add(run_id)
                if self._lease_store.release(tenant_id=tid, run_id=run_id, owner_id=runtime.owner_id):
                    released_runtime.add(run_id)

        for run_id, record in runtime_map.items():
            if run_id in released_runtime:
                continue
            admission = admission_map.get(run_id)
            if admission is None:
                if self._lease_store.release(tenant_id=tid, run_id=run_id, owner_id=record.owner_id):
                    released_runtime.add(run_id)

        post_runtime = self._lease_store.list_active(tenant_id=tid, now=moment)
        post_admission = self._admission_backend.list_active(tenant_id=tid)
        parity_report = self._checks.evaluate_semantic_parity(tenant_id=tid, leases=post_runtime, admissions=post_admission, now=moment)
        runtime_report = self._checks.evaluate_runtime_leases(tenant_id=tid, leases=post_runtime, limit=limit, now=moment)
        admission_report = self._checks.evaluate_admission_leases(tenant_id=tid, admissions=post_admission, limit=limit, now=moment)
        codes = tuple(
            sorted(
                {
                    item.code
                    for item in (*parity_report.violations, *runtime_report.violations, *admission_report.violations)
                }
            )
        )
        return TenantRuntimeReconciliationResult(
            tenant_id=tid,
            released_runtime_runs=tuple(sorted(released_runtime)),
            released_admission_runs=tuple(sorted(released_admission)),
            report_ok=parity_report.ok and runtime_report.ok and admission_report.ok,
            violation_codes=codes,
        )


__all__ = [
    'CANON_TENANT_RUNTIME_RECONCILIATION',
    'TenantRuntimeReconciliationResult',
    'TenantRuntimeReconciler',
]
