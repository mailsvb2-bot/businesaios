from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TenantAnalyticsRollup:
    tenant_id: str
    overall_state: str
    overall_score: float
    revenue_total: float = 0.0
    retention_ratio: float = 0.0
    execution_ratio: float = 0.0
    blocked_ratio: float = 0.0
    latency_p95_ms: int = 0


@dataclass(frozen=True)
class FleetAnalyticsRollup:
    tenant_count: int
    healthy_tenants: int
    warning_tenants: int
    critical_tenants: int
    average_score: float
    revenue_total: float = 0.0
    average_retention_ratio: float = 0.0
    average_execution_ratio: float = 0.0
    average_blocked_ratio: float = 0.0
    average_latency_p95_ms: float = 0.0
    top_risk_tenants: tuple[str, ...] = ()
    generated_at_ms: int = 0
    metadata: dict[str, str] = field(default_factory=dict)
