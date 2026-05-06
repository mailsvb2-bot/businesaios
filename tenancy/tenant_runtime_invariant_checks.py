from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_admission_contract import TenantAdmissionLease
from tenancy.tenant_backend_clock_policy import ensure_aware
from tenancy.tenant_runtime_lease_store import TenantRuntimeLeaseRecord


CANON_TENANT_RUNTIME_INVARIANT_CHECKS = True


@dataclass(frozen=True)
class TenantInvariantViolation:
    code: str
    tenant_id: str
    detail: str


@dataclass(frozen=True)
class TenantInvariantReport:
    tenant_id: str
    ok: bool
    violations: tuple[TenantInvariantViolation, ...]


class TenantRuntimeInvariantChecks:
    def evaluate_runtime_leases(
        self,
        *,
        tenant_id: str,
        leases: Sequence[TenantRuntimeLeaseRecord],
        limit: int | None = None,
        now: datetime | None = None,
    ) -> TenantInvariantReport:
        tid = require_tenant_id(tenant_id)
        moment = ensure_aware(now) if now is not None else None
        violations: list[TenantInvariantViolation] = []
        run_ids = Counter()
        tokens = Counter()
        previous_token = 0
        for lease in sorted(leases, key=lambda item: (item.fencing_token, item.run_id)):
            lease.validate()
            if require_tenant_id(lease.tenant_id) != tid:
                violations.append(TenantInvariantViolation('cross_tenant_lease', tid, f'run_id={lease.run_id}'))
            run_ids[lease.run_id] += 1
            tokens[int(lease.fencing_token)] += 1
            if int(lease.fencing_token) < previous_token:
                violations.append(TenantInvariantViolation('non_monotonic_fencing', tid, f'token={lease.fencing_token} previous={previous_token}'))
            previous_token = int(lease.fencing_token)
            if moment is not None and ensure_aware(lease.expires_at) <= moment:
                violations.append(TenantInvariantViolation('expired_active_lease', tid, f'run_id={lease.run_id}'))
        for run_id, count in sorted(run_ids.items()):
            if count > 1:
                violations.append(TenantInvariantViolation('duplicate_run_id', tid, f'run_id={run_id} count={count}'))
        for token, count in sorted(tokens.items()):
            if count > 1:
                violations.append(TenantInvariantViolation('duplicate_fencing_token', tid, f'token={token} count={count}'))
        if limit is not None and len(leases) > int(limit):
            violations.append(TenantInvariantViolation('tenant_limit_exceeded', tid, f'active={len(leases)} limit={int(limit)}'))
        return TenantInvariantReport(tenant_id=tid, ok=not violations, violations=tuple(violations))

    def evaluate_admission_leases(
        self,
        *,
        tenant_id: str,
        admissions: Sequence[TenantAdmissionLease],
        limit: int | None = None,
        now: datetime | None = None,
    ) -> TenantInvariantReport:
        tid = require_tenant_id(tenant_id)
        moment = ensure_aware(now) if now is not None else None
        violations: list[TenantInvariantViolation] = []
        run_ids = Counter()
        tokens = Counter()
        for lease in admissions:
            lease.validate()
            if require_tenant_id(lease.tenant_id) != tid:
                violations.append(TenantInvariantViolation('cross_tenant_admission', tid, f'run_id={lease.run_id}'))
            run_ids[lease.run_id] += 1
            tokens[int(lease.fencing_token)] += 1
            if moment is not None and ensure_aware(lease.expires_at) <= moment:
                violations.append(TenantInvariantViolation('expired_admission_lease', tid, f'run_id={lease.run_id}'))
        for run_id, count in sorted(run_ids.items()):
            if count > 1:
                violations.append(TenantInvariantViolation('duplicate_admission_run_id', tid, f'run_id={run_id} count={count}'))
        for token, count in sorted(tokens.items()):
            if count > 1:
                violations.append(TenantInvariantViolation('duplicate_admission_fencing', tid, f'token={token} count={count}'))
        if limit is not None and len(admissions) > int(limit):
            violations.append(TenantInvariantViolation('admission_limit_exceeded', tid, f'active={len(admissions)} limit={int(limit)}'))
        return TenantInvariantReport(tenant_id=tid, ok=not violations, violations=tuple(violations))

    def evaluate_semantic_parity(
        self,
        *,
        tenant_id: str,
        leases: Sequence[TenantRuntimeLeaseRecord],
        admissions: Sequence[TenantAdmissionLease],
        now: datetime | None = None,
    ) -> TenantInvariantReport:
        tid = require_tenant_id(tenant_id)
        moment = ensure_aware(now) if now is not None else None
        violations: list[TenantInvariantViolation] = []
        runtime_by_run = {item.run_id: item for item in leases}
        admission_by_run = {item.run_id: item for item in admissions}
        for run_id, runtime in runtime_by_run.items():
            runtime.validate()
            if require_tenant_id(runtime.tenant_id) != tid:
                violations.append(TenantInvariantViolation('cross_tenant_lease', tid, f'run_id={run_id}'))
                continue
            admission = admission_by_run.get(run_id)
            if admission is None:
                violations.append(TenantInvariantViolation('missing_admission_lease', tid, f'run_id={run_id}'))
                continue
            admission.validate()
            if require_tenant_id(admission.tenant_id) != tid:
                violations.append(TenantInvariantViolation('cross_tenant_admission', tid, f'run_id={run_id}'))
            if runtime.owner_id != admission.owner_id:
                violations.append(TenantInvariantViolation('owner_mismatch', tid, f'run_id={run_id}'))
            if int(runtime.fencing_token) != int(admission.fencing_token):
                violations.append(TenantInvariantViolation('fencing_mismatch', tid, f'run_id={run_id}'))
            if moment is not None and ensure_aware(runtime.expires_at) <= moment:
                violations.append(TenantInvariantViolation('expired_active_lease', tid, f'run_id={run_id}'))
            if moment is not None and ensure_aware(admission.expires_at) <= moment:
                violations.append(TenantInvariantViolation('expired_admission_lease', tid, f'run_id={run_id}'))
        for run_id in sorted(set(admission_by_run) - set(runtime_by_run)):
            violations.append(TenantInvariantViolation('orphan_admission_lease', tid, f'run_id={run_id}'))
        return TenantInvariantReport(tenant_id=tid, ok=not violations, violations=tuple(violations))


__all__ = [
    'CANON_TENANT_RUNTIME_INVARIANT_CHECKS',
    'TenantInvariantReport',
    'TenantInvariantViolation',
    'TenantRuntimeInvariantChecks',
]
