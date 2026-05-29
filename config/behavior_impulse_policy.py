from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImpulseBoundsPolicy:
    max_step: float = 0.25
    max_anti_step: float = 0.40
    ui_rage_anti_delta: float = 0.08
    ui_rage_trust_delta: float = -0.05
    fatigue_anti_delta: float = 0.05
    early_stop_progress_threshold: float = 0.25
    early_stop_anti_delta: float = 0.04
    offer_success_trust_delta: float = 0.06
    offer_success_payment_delta: float = 0.08
    offer_success_value_delta: float = 0.03
    offer_success_anti_delta: float = -0.06
    offer_failure_trust_delta: float = -0.04
    offer_failure_payment_delta: float = -0.04
    offer_failure_anti_delta: float = 0.06
    zero_value: float = 0.0


ImpulseTuple = tuple[float, float, float, float, float]


def default_event_impulse_tuples() -> dict[str, ImpulseTuple]:
    z = 0.0
    return {
        "ui_click": (0.02, z, z, z, z),
        "paywall_opened": (z, z, 0.03, 0.01, z),
        "paywall_closed": (z, -0.01, z, -0.01, 0.01),
        "offer_shown": (z, z, 0.03, 0.01, z),
        "offer_clicked": (0.04, z, 0.03, 0.05, z),
        "purchase_attempt": (0.03, z, 0.02, 0.05, z),
        "purchase_success": (z, 0.10, 0.05, 0.15, -0.10),
        "purchase_failed": (z, -0.08, z, -0.06, 0.10),
        "mood_logged": (0.01, 0.02, z, z, -0.01),
        "audio_sent": (z, z, 0.01, z, z),
        "audio_started": (0.01, z, 0.02, z, z),
        "audio_progress": (0.01, z, 0.02, z, z),
        "audio_completed": (z, 0.05, 0.06, z, -0.03),
        "audio_stopped": (z, z, z, z, z),
        "entitlement_granted": (z, 0.03, z, z, -0.02),
        "offer_outcome": (z, z, z, z, z),
        "decision_issued": (z, z, z, z, z),
        "ai_decision_trace": (z, z, z, z, z),
        "data_export": (z, z, z, z, z),
        "data_delete": (z, z, z, z, z),
        "rate_limited": (z, z, z, z, z),
    }


@dataclass(frozen=True)
class BehaviorImpulsePolicy:
    event_impulses: dict[str, ImpulseTuple] = field(default_factory=default_event_impulse_tuples)
    bounds: ImpulseBoundsPolicy = field(default_factory=ImpulseBoundsPolicy)


DEFAULT_IMPULSE_BOUNDS_POLICY = ImpulseBoundsPolicy()
