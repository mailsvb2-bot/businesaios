from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from config.world_model_defaults import DEFAULT_WORLD_MODEL_DEFAULTS
from core.world_model.enums import ReaderKind, SignalFreshness, SnapshotStatus

T = TypeVar("T")


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    reader: ReaderKind
    payload: T | None
    observed_at_ms: int | None
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_missing(self) -> bool:
        return self.payload is None


@dataclass(frozen=True)
class ReaderBundle:
    customer: ReadResult[dict]
    revenue: ReadResult[dict]
    campaign: ReadResult[dict]
    product: ReadResult[dict]
    messaging: ReadResult[dict]
    market: ReadResult[dict]


@dataclass(frozen=True)
class CustomerState:
    customer_id: str
    stage: str = DEFAULT_WORLD_MODEL_DEFAULTS.unknown_stage
    segment: str = DEFAULT_WORLD_MODEL_DEFAULTS.unknown_segment
    sessions_30d: int = DEFAULT_WORLD_MODEL_DEFAULTS.sessions_default
    purchases_30d: int = DEFAULT_WORLD_MODEL_DEFAULTS.purchases_default
    last_seen_at_ms: int | None = None
    traits: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductState:
    product_id: str
    title: str = DEFAULT_WORLD_MODEL_DEFAULTS.unknown_title
    price: float | None = None
    margin: float | None = None
    inventory_status: str = DEFAULT_WORLD_MODEL_DEFAULTS.unknown_inventory_status
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DemandState:
    level: str = DEFAULT_WORLD_MODEL_DEFAULTS.unknown_demand_level
    confidence: float = DEFAULT_WORLD_MODEL_DEFAULTS.demand_confidence_default
    revenue_7d: float = DEFAULT_WORLD_MODEL_DEFAULTS.demand_revenue_7d_default
    orders_7d: int = DEFAULT_WORLD_MODEL_DEFAULTS.demand_orders_7d_default
    conversion_rate: float | None = None
    campaign_pressure: float | None = None
    demand_trend: str = DEFAULT_WORLD_MODEL_DEFAULTS.unknown_demand_trend
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketState:
    channel: str
    geo: str
    competition_index: float | None = None
    cpm: float | None = None
    seasonality: str = DEFAULT_WORLD_MODEL_DEFAULTS.unknown_seasonality
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BusinessState:
    tenant_id: str
    business_id: str
    customer: CustomerState
    product: ProductState
    demand: DemandState
    market: MarketState
    messaging: dict[str, Any] = field(default_factory=dict)
    economics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StateBundle:
    business_state: BusinessState


@dataclass(frozen=True)
class FreshnessReport:
    per_reader: dict[str, SignalFreshness]
    age_ms: dict[str, int | None]
    worst_status: SignalFreshness


@dataclass(frozen=True)
class CompletenessReport:
    score: float
    missing_fields: tuple[str, ...]
    present_fields: tuple[str, ...]


@dataclass(frozen=True)
class ConfidenceReport:
    score: float
    freshness_weight: float
    completeness_weight: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class WorldSnapshot:
    tenant_id: str
    correlation_id: str
    confidence: float
    business_id: str = ""
    snapshot_id: str = ""
    built_at_ms: int = DEFAULT_WORLD_MODEL_DEFAULTS.world_snapshot_built_at_default
    schema_version: str = DEFAULT_WORLD_MODEL_DEFAULTS.world_snapshot_schema_version
    status: SnapshotStatus = SnapshotStatus.ACCEPTED
    business_state: BusinessState | None = None
    freshness: FreshnessReport | None = None
    completeness: CompletenessReport | None = None
    confidence_report: ConfidenceReport | None = None
    explain: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotRejection:
    snapshot_id: str
    tenant_id: str
    business_id: str
    built_at_ms: int
    schema_version: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldSnapshotRequest:
    tenant_id: str
    correlation_id: str


@dataclass(frozen=True)
class WorldModelBuildInput:
    tenant_id: str
    business_id: str
    customer_id: str
    product_id: str
    channel: str
    geo: str
    now_ms: int
    correlation_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldModelBuildResult:
    accepted: bool
    snapshot: WorldSnapshot | None = None
    rejection: SnapshotRejection | None = None
