from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


CANON_MARKET_INTELLIGENCE_ECONOMIC_CONTROL = True


@dataclass(frozen=True)
class TenantBudget:
    tenant_id: str
    daily_request_budget: int = 1000
    provider_spend_budget: float = 500.0
    burst_limit_per_minute: int = 100


@dataclass
class MarketIntelligenceEconomicControl:
    tenant_budgets: dict[str, TenantBudget] = field(default_factory=dict)
    request_counters: dict[tuple[str, str], int] = field(default_factory=dict)
    spend_counters: dict[tuple[str, str], float] = field(default_factory=dict)
    recent_requests: dict[tuple[str, str], deque[datetime]] = field(default_factory=dict)
    noisy_tenants: set[str] = field(default_factory=set)

    def ensure_allowed(self, *, tenant_id: str, provider: str, estimated_cost: float = 0.0) -> None:
        budget = self.tenant_budgets.get(tenant_id, TenantBudget(tenant_id=tenant_id))
        req_key = (tenant_id, provider)
        used_requests = int(self.request_counters.get(req_key, 0))
        used_spend = float(self.spend_counters.get(req_key, 0.0))
        recent = self._recent(req_key)
        if tenant_id in self.noisy_tenants:
            raise ValueError(f'tenant suppressed as noisy: {tenant_id}')
        if used_requests >= budget.daily_request_budget:
            raise ValueError(f'tenant request budget exhausted: {tenant_id}')
        if used_spend + estimated_cost > budget.provider_spend_budget:
            raise ValueError(f'tenant provider spend budget exhausted: {tenant_id}/{provider}')
        if len(recent) >= budget.burst_limit_per_minute:
            raise ValueError(f'tenant burst protection triggered: {tenant_id}')

    def record_usage(self, *, tenant_id: str, provider: str, cost: float) -> None:
        key = (tenant_id, provider)
        self.request_counters[key] = int(self.request_counters.get(key, 0)) + 1
        self.spend_counters[key] = float(self.spend_counters.get(key, 0.0)) + float(cost)
        recent = self._recent(key)
        recent.append(datetime.now(UTC))
        if len(recent) > 5 * self.tenant_budgets.get(tenant_id, TenantBudget(tenant_id=tenant_id)).burst_limit_per_minute:
            self.noisy_tenants.add(tenant_id)

    def fairness_priority(self, *, tenant_id: str, provider: str) -> float:
        key = (tenant_id, provider)
        used = float(self.request_counters.get(key, 0))
        return 1.0 / max(1.0, used + 1.0)

    def snapshot(self) -> dict[str, Any]:
        return {
            'request_counters': {f'{k[0]}:{k[1]}': v for k, v in self.request_counters.items()},
            'spend_counters': {f'{k[0]}:{k[1]}': v for k, v in self.spend_counters.items()},
            'noisy_tenants': sorted(self.noisy_tenants),
        }

    def _recent(self, key: tuple[str, str]) -> deque[datetime]:
        queue = self.recent_requests.setdefault(key, deque())
        cutoff = datetime.now(UTC) - timedelta(minutes=1)
        while queue and queue[0] < cutoff:
            queue.popleft()
        return queue
