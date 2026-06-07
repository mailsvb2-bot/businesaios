from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DashboardSectionState:
    section_id: str
    state: str
    score: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalyticsDashboard:
    tenant_id: str
    window_days: int
    overall_state: str
    overall_score: float
    sections: dict[str, DashboardSectionState] = field(default_factory=dict)
    highlights: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    generated_at_ms: int = 0
