from __future__ import annotations

"""Canonical AI CEO intent resolution.

Single source of truth for converting UI/runtime inputs into ``CEOIntentV1``.
This prevents planner-support helpers and runtime boot from inventing slightly
 different horizon/risk/objective parsing rules.
"""

from core.ai_ceo.contracts import CEOIntentV1

_ALLOWED_RISK = {"low", "medium", "high"}
_OBJECTIVE_ALIASES = {
    "growth": "increase_profit",
    "increase_profit": "increase_profit",
    "profit": "increase_profit",
    "profit_growth": "increase_profit",
    "steady_roi": "steady_roi",
    "roi": "steady_roi",
    "efficiency": "steady_roi",
    "reduce_risk": "reduce_risk",
    "risk": "reduce_risk",
    "safety": "reduce_risk",
}


def parse_horizon_days(value: str | int | None, *, default: int = 14) -> int:
    if isinstance(value, int):
        return max(1, int(value))
    text = str(value or "").strip().lower()
    if not text:
        return int(default)
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return int(default)
    return max(1, int(digits))


def normalize_risk(value: str | None, *, default: str = "low") -> str:
    risk = str(value or "").strip().lower()
    return risk if risk in _ALLOWED_RISK else default


def normalize_objective(value: str | None, *, default: str = "increase_profit") -> str:
    objective = str(value or "").strip().lower().replace("-", "_")
    return _OBJECTIVE_ALIASES.get(objective, default)


def build_intent(*, objective: str | None = None, horizon: str | int | None = None, risk_level: str | None = None) -> CEOIntentV1:
    return CEOIntentV1(
        kind=normalize_objective(objective),
        horizon_days=parse_horizon_days(horizon, default=14),
        risk_level=normalize_risk(risk_level, default="low"),
    )


def build_intent_from_session_args(*, args: str | None, objective: str | None = None) -> CEOIntentV1:
    text = str(args or "").strip()
    parts = [part for part in text.split() if part]
    horizon = parts[0] if parts else None
    risk = parts[1] if len(parts) >= 2 else None
    return build_intent(objective=objective, horizon=horizon, risk_level=risk)


def build_session_args(*, horizon: str | int | None, risk_level: str | None = None) -> str:
    days = parse_horizon_days(horizon, default=14)
    risk = normalize_risk(risk_level, default="low")
    return f"{days} {risk}"


__all__ = [
    "build_intent",
    "build_intent_from_session_args",
    "build_session_args",
    "normalize_objective",
    "normalize_risk",
    "parse_horizon_days",
]
