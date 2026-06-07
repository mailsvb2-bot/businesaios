from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScenarioInput:
    tenant_id: str
    scenario_name: str


@dataclass(frozen=True)
class ScenarioOutcome:
    tenant_id: str
    scenario_name: str
    confidence: float
    downside_risk: float


@dataclass(frozen=True)
class SimScore:
    score: float
    confidence: float
    debug: dict[str, Any]
