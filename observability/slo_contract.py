from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from core.tenancy.normalization import require_tenant_id


CANON_SLO_CONTRACT = True


class SLIKind(str, Enum):
    LATENCY_P50_MS = 'latency_p50_ms'
    LATENCY_P95_MS = 'latency_p95_ms'
    LATENCY_P99_MS = 'latency_p99_ms'
    ERROR_RATE = 'error_rate'
    AVAILABILITY = 'availability'
    SUCCESS_RATE = 'success_rate'
    THROUGHPUT = 'throughput'
    GAUGE = 'gauge'


class SLOComparator(str, Enum):
    LTE = 'lte'
    GTE = 'gte'


@dataclass(frozen=True)
class SLODefinition:
    slo_id: str
    tenant_id: str
    sli_name: str
    sli_kind: SLIKind
    comparator: SLOComparator
    target_value: float
    min_sample_count: int = 1
    description: str = ''
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.slo_id or '').strip():
            raise ValueError('slo_id is required')
        require_tenant_id(self.tenant_id)
        if not str(self.sli_name or '').strip():
            raise ValueError('sli_name is required')
        if int(self.min_sample_count) < 1:
            raise ValueError('min_sample_count must be >= 1')


@dataclass(frozen=True)
class SLIReading:
    tenant_id: str
    sli_name: str
    sli_kind: SLIKind
    value: float
    sample_count: int = 0
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.sli_name or '').strip():
            raise ValueError('sli_name is required')
        if int(self.sample_count) < 0:
            raise ValueError('sample_count must be >= 0')


@dataclass(frozen=True)
class SLOEvaluation:
    tenant_id: str
    slo_id: str
    sli_name: str
    observed_value: float
    target_value: float
    is_compliant: bool
    sample_count: int
    labels: Mapping[str, str] = field(default_factory=dict)

    @property
    def error_budget_consumed(self) -> float:
        if self.target_value == 0:
            return 0.0
        delta = abs(float(self.observed_value) - float(self.target_value))
        return max(0.0, delta / abs(float(self.target_value)))


__all__ = [
    'CANON_SLO_CONTRACT',
    'SLIKind',
    'SLIReading',
    'SLOComparator',
    'SLODefinition',
    'SLOEvaluation',
]
