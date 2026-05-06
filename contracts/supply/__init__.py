from __future__ import annotations

from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class BusinessCapacity:
    business_id: str = ""
    available_slots: int = 0
    max_parallel_jobs: int = 0
    utilization_ratio: float = 0.0
    overflow_risk: float = 0.0

@dataclass(frozen=True, slots=True)
class BusinessConversionState:
    business_id: str = ""
    lead_to_contact_rate: float = 0.0
    contact_to_sale_rate: float = 0.0
    close_rate_30d: float = 0.0

@dataclass(frozen=True, slots=True)
class BusinessLiveState:
    business_id: str = ""
    open_now: bool = False
    capacity_score: float = 0.0
    queue_load: float = 0.0
    response_speed_score: float = 0.0
    conversion_score: float = 0.0
    quality_score: float = 0.0
    risk_score: float = 0.0
    reputation_score: float = 0.0
    margin_score: float = 0.0
    features: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class BusinessPricePosition:
    business_id: str = ""
    price_band: str = ""
    relative_price_index: float = 0.0
    discount_flexibility: float = 0.0

@dataclass(frozen=True, slots=True)
class BusinessQualityState:
    business_id: str = ""
    customer_satisfaction: float = 0.0
    refund_rate: float = 0.0
    complaint_rate: float = 0.0
    repeat_rate: float = 0.0

@dataclass(frozen=True, slots=True)
class BusinessReputationState:
    business_id: str = ""
    review_score: float = 0.0
    review_count: int = 0
    verified_ratio: float = 0.0
    recent_negative_ratio: float = 0.0

@dataclass(frozen=True, slots=True)
class BusinessResponseState:
    business_id: str = ""
    median_first_response_min: float = 0.0
    response_rate_7d: float = 0.0
    no_response_rate_30d: float = 0.0

@dataclass(frozen=True, slots=True)
class BusinessRiskState:
    business_id: str = ""
    fraud_risk: float = 0.0
    refund_risk: float = 0.0
    policy_risk: float = 0.0
    manual_review_required: bool = False

@dataclass(frozen=True, slots=True)
class BusinessServiceArea:
    business_id: str = ""
    area_codes: tuple[str, ...] = ()
    max_radius_km: int = 0
    supports_remote: bool = False

@dataclass(frozen=True, slots=True)
class BusinessSupplyProfile:
    business_id: str = ""
    name: str = ""
    service_categories: tuple[str, ...] = ()
    service_area_codes: tuple[str, ...] = ()
    price_band: str = ""
    notification_channels: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    active: bool = False

__all__ = [
    'BusinessCapacity','BusinessConversionState','BusinessLiveState','BusinessPricePosition',
    'BusinessQualityState','BusinessReputationState','BusinessResponseState','BusinessRiskState',
    'BusinessServiceArea','BusinessSupplyProfile',
]
