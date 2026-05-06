from __future__ import annotations

ROLE_WEIGHTS: dict[str, float] = {
    "user": 0.8,
    "champion": 1.1,
    "decision_maker": 1.3,
    "finance": 1.2,
    "it": 1.0,
    "operator": 0.9,
}


def role_weight(role: str) -> float:
    return ROLE_WEIGHTS.get(role, 1.0)
