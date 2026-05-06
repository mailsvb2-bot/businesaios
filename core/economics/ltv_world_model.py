from __future__ import annotations

"""V13 LTV-oriented world model (pure & deterministic).

This module MUST NOT perform side-effects.
It is used only to derive decision features (e.g., predicted_ltv) that may
influence *policy proposals*. DecisionCore remains the ONLY brain.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UserState:
    user_id: str
    sessions: int
    payments: float
    last_seen: float


class LTVModel:
    """Minimal deterministic LTV predictor.

    Replace with ML regression in production.
    """

    def predict(self, user: UserState, *, now: float | None = None) -> float:
        # Keep the model deterministic even when callers forget to pass `now`.
        # Falling back to wall-clock time would introduce a hidden second time
        # source into decision enrichment.
        if now is None:
            now = float(user.last_seen) + 1.0
        recency = max(1.0, float(now) - float(user.last_seen))
        return float(user.payments) * 0.6 + float(user.sessions) * 0.3 + (1.0 / recency) * 100.0


@dataclass(frozen=True)
class LTVWorldState:
    user: UserState
    predicted_ltv: float


class WorldModel:
    def __init__(self, ltv_model: LTVModel):
        self.ltv_model = ltv_model

    @classmethod
    def from_ltv_model(cls, ltv_model: LTVModel | None = None) -> "WorldModel":
        return cls(ltv_model=ltv_model or LTVModel())

    def build(self, user: UserState, *, now: float | None = None) -> LTVWorldState:
        # Keep the world-model deterministic even when callers do not pass time.
        resolved_now = float(now) if now is not None else (float(user.last_seen) + 1.0)
        return LTVWorldState(user=user, predicted_ltv=float(self.ltv_model.predict(user, now=resolved_now)))


def build_ltv_world_model() -> WorldModel:
    """Canonical factory for boot wiring.

    Boot code should depend on this factory rather than constructing nested
    model objects inline. That keeps the world-model path explicit and avoids
    ad-hoc construction drift.
    """

    return WorldModel.from_ltv_model()


__all__ = ["UserState", "LTVModel", "LTVWorldState", "WorldModel", "build_ltv_world_model"]
