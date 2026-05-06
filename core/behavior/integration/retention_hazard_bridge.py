from __future__ import annotations

from core.behavior.math.vector_ops import clamp


def adjust_hazard_score(base_hazard: float, behavior_observables: dict[str, float]) -> float:
    anti = behavior_observables.get("anti_field_level", 0.0)
    fatigue = behavior_observables.get("fatigue_score", 0.0)
    coherence = behavior_observables.get("coherence_score", 0.0)
    adjusted = base_hazard * (1.0 + anti * 0.5 + fatigue * 0.25)
    adjusted *= 1.0 - coherence * 0.25
    return clamp(adjusted)
