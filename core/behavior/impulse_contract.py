from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.impulse_bounds_policy import DEFAULT_IMPULSE_BOUNDS_POLICY, ImpulseBoundsPolicy


@dataclass(frozen=True)
class Impulse:
    dI: float = 0.0
    dT: float = 0.0
    dV: float = 0.0
    dP: float = 0.0
    anti_impulse: float = 0.0

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        return (float(self.dI), float(self.dT), float(self.dV), float(self.dP), float(self.anti_impulse))


@dataclass(frozen=True)
class ImpulseApplication:
    event_type: str
    domain: str
    delta: Impulse
    source: str = "default_catalog"


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def apply_impulse(
    *,
    state: dict[str, Any],
    impulse: Impulse,
    policy: ImpulseBoundsPolicy = DEFAULT_IMPULSE_BOUNDS_POLICY,
) -> dict[str, float]:
    z = DEFAULT_IMPULSE_BOUNDS_POLICY.zero_value
    return {
        "intent": clamp01(float(state.get("intent", z)) + impulse.dI),
        "trust": clamp01(float(state.get("trust", z)) + impulse.dT),
        "value": clamp01(float(state.get("value", z)) + impulse.dV),
        "permission": clamp01(float(state.get("permission", z)) + impulse.dP),
        "anti_impulse": clamp01(float(state.get("anti_impulse", z)) + impulse.anti_impulse),
    }


def impulse_for_event(
    *,
    event: dict[str, Any],
    policy: ImpulseBoundsPolicy = DEFAULT_IMPULSE_BOUNDS_POLICY,
) -> Impulse:
    et = str(event.get("event_type") or event.get("type") or "").strip()
    payload = event.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    base_tuple = policy.event_impulses.get(et)
    if base_tuple is None:
        z = DEFAULT_IMPULSE_BOUNDS_POLICY.zero_value
        return Impulse(z, z, z, z, z)

    dI, dT, dV, dP, anti = Impulse(*base_tuple).as_tuple()
    z = DEFAULT_IMPULSE_BOUNDS_POLICY.zero_value

    # Payload-sensitive refinements (bounded).
    if et == "ui_click" and float(payload.get("rage", z) or z) > z:
        anti += policy.bounds.ui_rage_anti_delta
        dT += policy.bounds.ui_rage_trust_delta

    if et in {"offer_shown", "paywall_opened"} and float(payload.get("fatigue", z) or z) > z:
        anti += policy.bounds.fatigue_anti_delta

    if et == "audio_stopped":
        # early-stop penalty is applied only if pos/len is known.
        pos = float(payload.get("pos_s") or z)
        length = float(payload.get("length_s") or z)
        if length > z and (pos / length) < policy.bounds.early_stop_progress_threshold:
            anti += policy.bounds.early_stop_anti_delta

    if et == "offer_outcome":
        # A unified, stable event that can be emitted by timeouts/jobs.
        outcome = str(payload.get("outcome") or "").strip().lower()
        if outcome in {"accepted", "paid", "converted"}:
            dV += policy.bounds.outcome_accept_value_delta
            dT += policy.bounds.outcome_accept_trust_delta
        elif outcome in {"dismissed", "ignored", "timeout"}:
            anti += policy.bounds.outcome_dismiss_anti_delta

    return Impulse(dI=dI, dT=dT, dV=dV, dP=dP, anti_impulse=anti)
