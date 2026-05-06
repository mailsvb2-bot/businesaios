from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import math
from typing import Mapping, Protocol

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_METRICS_CONTRACT = True
_ALLOWED_METRIC_TYPES = {"counter", "gauge", "histogram", "event"}


class TenantMetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    EVENT = "event"

    @classmethod
    def normalize(cls, value: str) -> str:
        text = _normalize_text(value, field_name="metric_type")
        if text not in _ALLOWED_METRIC_TYPES:
            raise ValueError("metric_type is invalid")
        return text


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def normalize_labels(labels: Mapping[str, str] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in dict(labels or {}).items():
        normalized[_normalize_text(key, field_name="label key")] = _normalize_text(value, field_name="label value")
    return normalized


def labels_signature(labels: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    normalized = normalize_labels(labels)
    return tuple(sorted(normalized.items()))


@dataclass(frozen=True)
class TenantMetricPoint:
    tenant_id: str
    metric_name: str
    value: float
    metric_type: str
    emitted_at: datetime = field(default_factory=utc_now)
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        _normalize_text(self.metric_name, field_name="metric_name")
        TenantMetricType.normalize(self.metric_type)
        numeric_value = float(self.value)
        if not math.isfinite(numeric_value):
            raise ValueError("value must be finite")
        if self.emitted_at.tzinfo is None or self.emitted_at.utcoffset() is None:
            raise ValueError("emitted_at must be timezone-aware")
        normalize_labels(self.labels)

    @property
    def series_signature(self) -> tuple[tuple[str, str], ...]:
        return labels_signature(self.labels)


@dataclass(frozen=True)
class TenantMetricAggregate:
    tenant_id: str
    metric_name: str
    sample_count: int
    total: float
    minimum: float
    maximum: float
    last_value: float
    last_emitted_at: datetime | None
    labels: Mapping[str, str] = field(default_factory=dict)
    label_series_count: int = 1
    labels_collapsed: bool = False

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        _normalize_text(self.metric_name, field_name="metric_name")
        sample_count = int(self.sample_count)
        if sample_count < 0:
            raise ValueError("sample_count must be >= 0")
        if int(self.label_series_count) <= 0:
            raise ValueError("label_series_count must be > 0")
        for field_name in ("total", "minimum", "maximum", "last_value"):
            numeric = float(getattr(self, field_name))
            if not math.isfinite(numeric):
                raise ValueError(f"{field_name} must be finite")
        if sample_count == 0:
            raise ValueError("sample_count must be > 0 for aggregate")
        if float(self.minimum) > float(self.maximum):
            raise ValueError("minimum must be <= maximum")
        if not (float(self.minimum) <= float(self.last_value) <= float(self.maximum)):
            raise ValueError("last_value must be within [minimum, maximum]")
        if self.last_emitted_at is not None and (self.last_emitted_at.tzinfo is None or self.last_emitted_at.utcoffset() is None):
            raise ValueError("last_emitted_at must be timezone-aware")
        normalize_labels(self.labels)


class TenantMetricsStoreContract(Protocol):
    def append(self, point: TenantMetricPoint) -> TenantMetricPoint: ...
    def increment(self, *, tenant_id: str, metric_name: str, amount: float = 1.0, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> TenantMetricPoint: ...
    def list_points(self, *, tenant_id: str, metric_name: str | None = None, since: datetime | None = None) -> tuple[TenantMetricPoint, ...]: ...
    def aggregate(self, *, tenant_id: str, metric_name: str, since: datetime | None = None) -> TenantMetricAggregate | None: ...


__all__ = [
    "CANON_TENANT_METRICS_CONTRACT",
    "TenantMetricAggregate",
    "TenantMetricType",
    "TenantMetricPoint",
    "TenantMetricsStoreContract",
    "labels_signature",
    "normalize_labels",
    "utc_now",
]
