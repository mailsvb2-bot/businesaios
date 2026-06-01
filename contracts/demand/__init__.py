from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.types import ensure_jsonable


@dataclass(frozen=True, slots=True)
class ClientBudget:
    currency: str = ""
    min_budget: float | None = None
    max_budget: float | None = None
    band: str = ""
    is_price_sensitive: bool = False

@dataclass(frozen=True, slots=True)
class ClientChannelOrigin:
    origin: str = ""
    medium: str = ""
    campaign: str = ""
    surface: str = ""
    raw_referrer: str = ""

@dataclass(frozen=True, slots=True)
class ClientConstraints:
    must_be_local: bool = False
    max_radius_km: int = 0
    exclude_business_ids: tuple[str, ...] = ()
    preferred_business_ids: tuple[str, ...] = ()
    hard_budget_ceiling: float | None = None
    required_time_window: str = ""

@dataclass(frozen=True, slots=True)
class ClientContext:
    customer_id: str = ""
    session_id: str = ""
    history_size: int = 0
    preferred_channels: tuple[str, ...] = ()
    last_route_business_id: str | None = None
    traits: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ClientIntent:
    service_type: str = ""
    urgency: str = ""
    budget_band: str = ""
    quality_band: str = ""
    location_hint: str = ""
    confidence: float = 0.0
    is_repeat_customer: bool = False
    needs_trust: bool = False
    is_high_value: bool = False
    raw_labels: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class ClientIntentSignal:
    signal_name: str = ""
    signal_value: str = ""
    confidence: float = 0.0
    source: str = ""

@dataclass(frozen=True, slots=True)
class ClientLocation:
    city: str = ""
    region: str = ""
    country: str = ""
    lat: float | None = None
    lon: float | None = None
    radius_km: int = 0

@dataclass(frozen=True, slots=True)
class ClientPriority:
    priority_code: str = ""
    priority_weight: float = 0.0
    reason: str = ""

@dataclass(frozen=True, slots=True)
class ClientQualityExpectation:
    band: str = ""
    requires_verified_reviews: bool = False
    requires_fast_response: bool = False
    confidence: float = 0.0

@dataclass(frozen=True, slots=True)
class ClientRequest:
    request_id: str = ""
    text: str = ""
    channel: str = ""
    created_at_ms: int = 0
    customer_id: str = ""
    session_id: str = ""
    location_hint: str = ""
    budget_hint: str = ""
    urgency_hint: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ClientSession:
    session_id: str = ""
    customer_id: str = ""
    first_seen_ms: int = 0
    last_seen_ms: int = 0
    touchpoints: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class ClientTimeUrgency:
    urgency_code: str = ""
    target_window: str = ""
    must_start_before_ms: int | None = None
    confidence: float = 0.0

@dataclass(frozen=True)
class DemandFlowBundle:
    request: Any
    intent: Any
    supply_profiles: tuple[Any, ...]
    live_states: tuple[Any, ...]
    gravity_snapshot: dict[str, object]
    match_bundle: Any
    routing_preparation: dict[str, object]
    decision: Any
    delivery: Any

    def as_dict(self) -> dict[str, object]:
        return {
            'request': self.request,
            'intent': self.intent,
            'supply_profiles': self.supply_profiles,
            'live_states': self.live_states,
            'gravity_snapshot': dict(self.gravity_snapshot),
            'match_bundle': self.match_bundle,
            'routing_preparation': dict(self.routing_preparation),
            'decision': self.decision,
            'delivery': self.delivery,
        }

    def as_jsonable(self) -> dict[str, object]:
        return ensure_jsonable(self.as_dict())

__all__ = [
    'ClientBudget','ClientChannelOrigin','ClientConstraints','ClientContext','ClientIntent',
    'ClientIntentSignal','ClientLocation','ClientPriority','ClientQualityExpectation',
    'ClientRequest','ClientSession','ClientTimeUrgency','DemandFlowBundle',
]
