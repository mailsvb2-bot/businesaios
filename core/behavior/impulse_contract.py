"""Canonical impulse contract for BusinesAIOS Behavioral OS.

This module defines a *portable* mapping from canonical event types
to small bounded impulses in the 4D behavioral spacetime:

  (I, T, V, P) + anti

I: intent / need
T: trust / risk
V: value recognition
P: payment readiness

The goal is not to "fit" weights, but to provide a strict, testable,
domain-agnostic *baseline physics* for Ring/DecisionCore.
Products may override via configuration, but must keep bounds.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from config.behavior_impulse_policy import (
    DEFAULT_IMPULSE_BOUNDS_POLICY,
    BehaviorImpulsePolicy,
)
from core.retention.event_types import normalize_event_type


@dataclass(frozen=True)
class Impulse:
    dI: float
    dT: float
    dV: float
    dP: float
    anti: float

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        return (float(self.dI), float(self.dT), float(self.dV), float(self.dP), float(self.anti))


def _clip(x: float, lo: float, hi: float) -> float:
    x = float(x)
    if x < lo:
        return float(lo)
    if x > hi:
        return float(hi)
    return float(x)


# Hard bounds for a *single* impulse application.
# Kept intentionally small; dynamics accumulate through repeated exposure.
MAX_STEP = DEFAULT_IMPULSE_BOUNDS_POLICY.max_step
MAX_ANTI_STEP = DEFAULT_IMPULSE_BOUNDS_POLICY.max_anti_step


def _event_impulses_from_policy(policy: BehaviorImpulsePolicy) -> dict[str, Impulse]:
    return {name: Impulse(*values) for name, values in policy.event_impulses.items()}


DEFAULT_IMPULSE_POLICY = BehaviorImpulsePolicy()
EVENT_IMPULSES: dict[str, Impulse] = _event_impulses_from_policy(DEFAULT_IMPULSE_POLICY)


def impulse_for_event(
    event: Mapping[str, Any],
    *,
    policy: BehaviorImpulsePolicy = DEFAULT_IMPULSE_POLICY,
) -> tuple[float, float, float, float, float]:
    """Return bounded (dI,dT,dV,dP,anti) for a canonical event.

    - Unknown events map to zeros (must not break runtime).
    - offer_outcome selects a specific impulse based on payload.success.
    - Some impulses are payload-sensitive (rage, fatigue, early_stop).
    """

    et_raw = str(event.get("event_type") or "")
    et = normalize_event_type(et_raw)
    payload = event.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    base_tuple = policy.event_impulses.get(et)
    if base_tuple is None:
        z = DEFAULT_IMPULSE_BOUNDS_POLICY.zero_value
        return (z, z, z, z, z)

    dI, dT, dV, dP, anti = Impulse(*base_tuple).as_tuple()
    z = DEFAULT_IMPULSE_BOUNDS_POLICY.zero_value

    # Payload-sensitive refinements (bounded).
    if et == "ui_click":
        if float(payload.get("rage", z) or z) > z:
            anti += policy.bounds.ui_rage_anti_delta
            dT += policy.bounds.ui_rage_trust_delta

    if et in {"offer_shown", "paywall_opened"}:
        if float(payload.get("fatigue", z) or z) > z:
            anti += policy.bounds.fatigue_anti_delta

    if et == "audio_stopped":
        # early-stop penalty is applied only if pos/len is known.
        pos = float(payload.get("pos_s") or z)
        length = float(payload.get("length_s") or z)
        if length > z and (pos / length) < policy.bounds.early_stop_progress_threshold:
            anti += policy.bounds.early_stop_anti_delta

    if et == "offer_outcome":
        # A unified, stable event that can be emitted by timeouts/jobs.
        success = bool(payload.get("success"))
        if success:
            dT += policy.bounds.offer_success_trust_delta
            dP += policy.bounds.offer_success_payment_delta
            dV += policy.bounds.offer_success_value_delta
            anti += policy.bounds.offer_success_anti_delta
        else:
            dT += policy.bounds.offer_failure_trust_delta
            dP += policy.bounds.offer_failure_payment_delta
            anti += policy.bounds.offer_failure_anti_delta

    # Final hard clipping.
    dI = _clip(dI, -MAX_STEP, MAX_STEP)
    dT = _clip(dT, -MAX_STEP, MAX_STEP)
    dV = _clip(dV, -MAX_STEP, MAX_STEP)
    dP = _clip(dP, -MAX_STEP, MAX_STEP)
    anti = _clip(anti, -MAX_ANTI_STEP, MAX_ANTI_STEP)
    return (float(dI), float(dT), float(dV), float(dP), float(anti))
