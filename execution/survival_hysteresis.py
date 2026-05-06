from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANON_SURVIVAL_HYSTERESIS = True


@dataclass(frozen=True, slots=True)
class SurvivalModeTransition:
    current_mode: str
    recommended_mode: str
    changed: bool
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"current_mode": self.current_mode, "recommended_mode": self.recommended_mode, "changed": bool(self.changed), "rationale": self.rationale, "metadata": dict(self.metadata)}


class SurvivalHysteresis:
    def recommend(self, *, current_mode: str, confidence: float, runway_days_after_action: float) -> SurvivalModeTransition:
        normalized = str(current_mode or "normal")
        if runway_days_after_action < 30.0 or confidence < 0.35:
            recommended = "survival"
            rationale = "low_runway_or_low_confidence"
        elif runway_days_after_action < 60.0 or confidence < 0.55:
            recommended = "defensive"
            rationale = "moderate_runway_pressure"
        elif normalized in {"survival", "defensive"} and runway_days_after_action < 90.0:
            recommended = normalized
            rationale = "sticky_hysteresis"
        else:
            recommended = "normal"
            rationale = "healthy_runway_and_confidence"
        return SurvivalModeTransition(
            current_mode=normalized,
            recommended_mode=recommended,
            changed=recommended != normalized,
            rationale=rationale,
            metadata={"owner": "execution.survival_hysteresis"},
        )


__all__ = ["CANON_SURVIVAL_HYSTERESIS", "SurvivalHysteresis", "SurvivalModeTransition"]
