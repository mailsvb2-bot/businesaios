from __future__ import annotations

from typing import Mapping


def _unit(v: object) -> float:
    return max(0.0, min(1.0, float(v or 0.0)))


def build_user_state(observables: Mapping[str, object]) -> dict[str, float]:
    return {
        "intent": _unit(observables.get("intent_index")),
        "trust": _unit(observables.get("trust_index")),
        "value_recognition": _unit(observables.get("value_index")),
        "payment_readiness": _unit(observables.get("payment_readiness_index")),
        "fatigue": _unit(observables.get("fatigue_index")),
        "hesitation": _unit(observables.get("hesitation_score")),
        "buy_vector": _unit(observables.get("buy_vector")),
        "churn_vector": _unit(observables.get("churn_vector")),
        "behavior_coherence": _unit(observables.get("coherence_score")),
    }
