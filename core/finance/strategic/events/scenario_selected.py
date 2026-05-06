from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioSelected:
    scenario_name: str
