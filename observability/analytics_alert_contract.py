from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class AnalyticsAlert:
    alert_id: str
    tenant_id: str
    source_kind: str
    severity: str
    summary: str
    metric_id: str = ''
    threshold_value: float = 0.0
    observed_value: float = 0.0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalyticsAlertBatch:
    tenant_id: str
    alerts: Tuple[AnalyticsAlert, ...] = ()
    generated_at_ms: int = 0
