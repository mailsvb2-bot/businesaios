from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from core.product.enums import FeatureStatus, FeatureType


@dataclass(frozen=True)
class ProductFeature:
    """Minimal feature descriptor for build/roadmap handlers."""

    feature_id: str
    name: str
    impact_score: float = 0.0


@dataclass(frozen=True)
class FeatureMetric:
    name: str
    value: float


@dataclass(frozen=True)
class FeatureRecord:
    feature_id: str
    name: str
    feature_type: FeatureType
    status: FeatureStatus
    adoption_rate: float = 0.0
    retention_delta: float = 0.0
    revenue_delta: float = 0.0
    effort_points: float = 0.0
    risk_score: float = 0.0
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureScore:
    feature_id: str
    value_score: float
    retention_score: float
    complexity_score: float
    risk_score: float
    total_score: float
