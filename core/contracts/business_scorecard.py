from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FunnelSnapshot:
    visitors: int = 0
    offer_shown: int = 0
    offer_clicked: int = 0
    purchase_attempt: int = 0
    purchase_success: int = 0
    offer_ctr: float = 0.0
    purchase_rate_from_click: float = 0.0
    visitor_to_purchase_rate: float = 0.0


@dataclass(frozen=True)
class RevenueSnapshot:
    purchase_success_count: int = 0
    purchase_failed_count: int = 0
    revenue_total: float = 0.0
    average_order_value: float = 0.0


@dataclass(frozen=True)
class RetentionSnapshot:
    active_users: int = 0
    returning_users: int = 0
    retention_ratio: float = 0.0
    churn_ratio: float = 0.0


@dataclass(frozen=True)
class DecisionSnapshot:
    issued_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    execution_ratio: float = 0.0
    blocked_ratio: float = 0.0


@dataclass(frozen=True)
class LatencySnapshot:
    sample_count: int = 0
    p50_ms: int = 0
    p95_ms: int = 0
    p99_ms: int = 0
    health_state: str = "unknown"


@dataclass(frozen=True)
class AnalyticsDiagnosis:
    overall_state: str
    score: float
    reasons: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BusinessScorecard:
    tenant_id: str
    window_days: int
    traffic_users: int
    funnel: FunnelSnapshot
    revenue: RevenueSnapshot
    retention: RetentionSnapshot
    decisions: DecisionSnapshot
    latency: LatencySnapshot
    diagnosis: AnalyticsDiagnosis
    generated_at_ms: int
    metadata: dict[str, str] = field(default_factory=dict)
