"""Tenant-fair claim planning for shared runtime queues.

Operational only:
- allocates existing queue claim-budget across tenants;
- does not invent jobs;
- does not change business semantics or DecisionCore outputs;
- prevents queue monopolization by one noisy tenant.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from collections.abc import Iterable

from core.tenancy.normalization import require_tenant_id
from runtime.queue.job_contract import normalize_now

CANON_RUNTIME_QUEUE_TENANT_FAIR_SCHEDULER = True


@dataclass(frozen=True)
class TenantQueuePressure:
    tenant_id: str
    queue_name: str
    pending_jobs: int
    active_claims: int = 0
    weight: int = 1
    oldest_pending_age_seconds: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_tenant_id(self.tenant_id))
        queue_name = str(self.queue_name).strip()
        if not queue_name:
            raise ValueError("queue_name is required")
        object.__setattr__(self, "queue_name", queue_name)
        for field_name in ("pending_jobs", "active_claims", "weight", "oldest_pending_age_seconds"):
            object.__setattr__(self, field_name, int(getattr(self, field_name)))
        if self.pending_jobs < 0:
            raise ValueError("pending_jobs must be >= 0")
        if self.active_claims < 0:
            raise ValueError("active_claims must be >= 0")
        if self.weight < 1:
            raise ValueError("weight must be >= 1")
        if self.oldest_pending_age_seconds < 0:
            raise ValueError("oldest_pending_age_seconds must be >= 0")


@dataclass(frozen=True)
class TenantFairAllocation:
    tenant_id: str
    queue_name: str
    claim_limit: int
    fairness_score: int
    pending_jobs: int
    active_claims: int
    starving: bool
    reason: str


@dataclass(frozen=True)
class TenantFairScheduleReport:
    queue_name: str
    total_claim_budget: int
    allocated_claims: int
    remaining_budget: int
    starving_tenants: int
    allocations: tuple[TenantFairAllocation, ...]

    @property
    def has_unallocated_budget(self) -> bool:
        return int(self.remaining_budget) > 0


class TenantFairScheduler:
    """Weighted fair scheduler with anti-starvation pre-pass."""

    def __init__(
        self,
        *,
        default_total_claim_limit: int = 32,
        default_quantum: int = 1,
        max_claims_per_tenant: int = 8,
        active_claim_penalty: int = 1,
        starvation_age_seconds: int = 120,
        starvation_boost_weight: int = 2,
    ) -> None:
        self._default_total_claim_limit = max(1, int(default_total_claim_limit))
        self._default_quantum = max(1, int(default_quantum))
        self._max_claims_per_tenant = max(1, int(max_claims_per_tenant))
        self._active_claim_penalty = max(0, int(active_claim_penalty))
        self._starvation_age_seconds = max(1, int(starvation_age_seconds))
        self._starvation_boost_weight = max(1, int(starvation_boost_weight))
        self._deficit: dict[tuple[str, str], int] = {}
        self._lock = RLock()

    def plan_allocations(
        self,
        *,
        queue_name: str,
        pressures: Iterable[TenantQueuePressure],
        total_claim_limit: int | None = None,
        now=None,
    ) -> TenantFairScheduleReport:
        normalize_now(now)
        queue = str(queue_name).strip()
        if not queue:
            raise ValueError("queue_name is required")
        budget = self._default_total_claim_limit if total_claim_limit is None else max(1, int(total_claim_limit))
        items = self._normalize_inputs(queue_name=queue, pressures=tuple(pressures))
        if not items:
            return TenantFairScheduleReport(
                queue_name=queue,
                total_claim_budget=budget,
                allocated_claims=0,
                remaining_budget=budget,
                starving_tenants=0,
                allocations=(),
            )

        with self._lock:
            allocations: dict[str, int] = {item.tenant_id: 0 for item in items}
            credits = {(item.tenant_id, item.queue_name): max(0, int(self._deficit.get((item.tenant_id, item.queue_name), 0))) for item in items}
            remaining_budget = budget

            starving_items = tuple(item for item in sorted(items, key=self._starvation_sort_key) if self._is_starving(item))
            for item in starving_items:
                if remaining_budget <= 0:
                    break
                cap = self._tenant_cap(item)
                if cap <= 0:
                    continue
                allocations[item.tenant_id] += 1
                remaining_budget -= 1

            weighted_order = tuple(sorted(items, key=self._weighted_sort_key))
            progressed = True
            while remaining_budget > 0 and progressed:
                progressed = False
                for item in weighted_order:
                    key = (item.tenant_id, item.queue_name)
                    if allocations[item.tenant_id] >= self._tenant_cap(item):
                        continue
                    credits[key] += self._quantum_for(item)
                    while credits[key] > 0 and remaining_budget > 0 and allocations[item.tenant_id] < self._tenant_cap(item):
                        allocations[item.tenant_id] += 1
                        credits[key] -= 1
                        remaining_budget -= 1
                        progressed = True
                    if remaining_budget <= 0:
                        break

            results: list[TenantFairAllocation] = []
            for item in sorted(items, key=self._report_sort_key):
                key = (item.tenant_id, item.queue_name)
                self._deficit[key] = max(0, int(credits[key]))
                granted = int(allocations[item.tenant_id])
                results.append(
                    TenantFairAllocation(
                        tenant_id=item.tenant_id,
                        queue_name=item.queue_name,
                        claim_limit=granted,
                        fairness_score=self._fairness_score(item),
                        pending_jobs=item.pending_jobs,
                        active_claims=item.active_claims,
                        starving=self._is_starving(item),
                        reason="fair_share_allocated" if granted > 0 else "fair_share_skipped",
                    )
                )

            allocated = sum(item.claim_limit for item in results)
            return TenantFairScheduleReport(
                queue_name=queue,
                total_claim_budget=budget,
                allocated_claims=allocated,
                remaining_budget=max(0, budget - allocated),
                starving_tenants=sum(1 for item in results if item.starving),
                allocations=tuple(results),
            )

    def reset(self, *, tenant_id: str | None = None, queue_name: str | None = None) -> None:
        with self._lock:
            if tenant_id is None and queue_name is None:
                self._deficit.clear()
                return
            normalized_tenant = require_tenant_id(tenant_id) if tenant_id is not None else None
            normalized_queue = str(queue_name).strip() if queue_name is not None else None
            if normalized_queue == "":
                raise ValueError("queue_name must not be blank when provided")
            doomed = [
                key
                for key in tuple(self._deficit.keys())
                if (normalized_tenant is None or key[0] == normalized_tenant)
                and (normalized_queue is None or key[1] == normalized_queue)
            ]
            for key in doomed:
                self._deficit.pop(key, None)

    def _normalize_inputs(self, *, queue_name: str, pressures: tuple[TenantQueuePressure, ...]) -> tuple[TenantQueuePressure, ...]:
        seen: set[str] = set()
        prepared: list[TenantQueuePressure] = []
        for item in pressures:
            if item.queue_name != queue_name:
                raise ValueError(f"cross-queue pressure set is forbidden: expected queue={queue_name} got queue={item.queue_name}")
            if item.tenant_id in seen:
                raise ValueError(f"duplicate tenant pressure entry: {item.tenant_id}")
            seen.add(item.tenant_id)
            if item.pending_jobs <= 0:
                continue
            prepared.append(item)
        return tuple(prepared)

    def _tenant_cap(self, item: TenantQueuePressure) -> int:
        return min(self._max_claims_per_tenant, int(item.pending_jobs))

    def _is_starving(self, item: TenantQueuePressure) -> bool:
        return int(item.pending_jobs) > 0 and int(item.oldest_pending_age_seconds) >= self._starvation_age_seconds

    def _quantum_for(self, item: TenantQueuePressure) -> int:
        return max(1, self._default_quantum * self._fairness_score(item))

    def _fairness_score(self, item: TenantQueuePressure) -> int:
        starvation_bonus = self._starvation_boost_weight if self._is_starving(item) else 0
        active_penalty = int(item.active_claims) * self._active_claim_penalty
        return max(1, int(item.weight) + int(starvation_bonus) - int(active_penalty))

    @staticmethod
    def _starvation_sort_key(item: TenantQueuePressure) -> tuple[int, int, str]:
        return (-int(item.oldest_pending_age_seconds), int(item.active_claims), item.tenant_id)

    def _weighted_sort_key(self, item: TenantQueuePressure) -> tuple[int, int, int, str]:
        return (-self._fairness_score(item), -int(item.oldest_pending_age_seconds), int(item.active_claims), item.tenant_id)

    @staticmethod
    def _report_sort_key(item: TenantQueuePressure) -> tuple[int, int, str]:
        return (-int(item.pending_jobs), -int(item.oldest_pending_age_seconds), item.tenant_id)


__all__ = [
    "CANON_RUNTIME_QUEUE_TENANT_FAIR_SCHEDULER",
    "TenantFairAllocation",
    "TenantFairScheduleReport",
    "TenantFairScheduler",
    "TenantQueuePressure",
]
