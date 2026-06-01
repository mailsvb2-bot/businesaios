from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class ExplainabilityEvidence:
    evidence_id: str
    category: str
    metric_id: str
    value: float | int | str
    note: str = ""


@dataclass(frozen=True)
class ExplainabilityReason:
    reason_id: str
    severity: str
    summary: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalyticsExplainabilityTrace:
    tenant_id: str
    trace_kind: str
    reasons: list[ExplainabilityReason] = field(default_factory=list)
    evidence: dict[str, ExplainabilityEvidence] = field(default_factory=dict)
    generated_at_ms: int = 0
