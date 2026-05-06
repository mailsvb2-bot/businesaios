from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Mapping

from core.tenancy.normalization import require_tenant_id


CANON_ALERT_RULE_CONTRACT = True


class AlertSeverity(str, Enum):
    INFO = 'info'
    WARNING = 'warning'
    HIGH = 'high'
    CRITICAL = 'critical'


class AlertComparator(str, Enum):
    GT = 'gt'
    GTE = 'gte'
    LT = 'lt'
    LTE = 'lte'
    EQ = 'eq'


@dataclass(frozen=True)
class AlertWindow:
    seconds: int = 300

    def validate(self) -> None:
        if int(self.seconds) <= 0:
            raise ValueError('window seconds must be > 0')

    @property
    def duration(self) -> timedelta:
        return timedelta(seconds=int(self.seconds))


@dataclass(frozen=True)
class AlertRule:
    rule_id: str
    tenant_id: str
    metric_name: str
    comparator: AlertComparator
    threshold: float
    severity: AlertSeverity
    window: AlertWindow = field(default_factory=AlertWindow)
    min_sample_count: int = 1
    dedup_key_suffix: str = ''
    labels: Mapping[str, str] = field(default_factory=dict)
    description: str = ''

    def validate(self) -> None:
        if not str(self.rule_id or '').strip():
            raise ValueError('rule_id is required')
        require_tenant_id(self.tenant_id)
        if not str(self.metric_name or '').strip():
            raise ValueError('metric_name is required')
        self.window.validate()
        if int(self.min_sample_count) < 1:
            raise ValueError('min_sample_count must be >= 1')


@dataclass(frozen=True)
class AlertEvaluationInput:
    tenant_id: str
    metric_name: str
    metric_value: float
    sample_count: int
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.metric_name or '').strip():
            raise ValueError('metric_name is required')
        if int(self.sample_count) < 0:
            raise ValueError('sample_count must be >= 0')


@dataclass(frozen=True)
class AlertMatch:
    tenant_id: str
    rule_id: str
    metric_name: str
    observed_value: float
    threshold: float
    severity: AlertSeverity
    description: str
    sample_count: int
    labels: Mapping[str, str] = field(default_factory=dict)

    def dedup_key(self) -> str:
        label_part = '|'.join(f"{k}={v}" for k, v in sorted(self.labels.items()))
        return f"{self.tenant_id}:{self.rule_id}:{self.metric_name}:{self.severity.value}:{label_part}"


__all__ = [
    'AlertComparator',
    'AlertEvaluationInput',
    'AlertMatch',
    'AlertRule',
    'AlertSeverity',
    'AlertWindow',
    'CANON_ALERT_RULE_CONTRACT',
]
