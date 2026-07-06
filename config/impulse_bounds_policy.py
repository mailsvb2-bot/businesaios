from __future__ import annotations

from dataclasses import dataclass, field

CANON_IMPULSE_BOUNDS_POLICY = True


@dataclass(frozen=True)
class ImpulseBounds:
    """Bounded behavior impulse refinements used by the Dirac behavior layer."""

    ui_rage_anti_delta: float = 0.10
    ui_rage_trust_delta: float = -0.05
    fatigue_anti_delta: float = 0.05
    early_stop_progress_threshold: float = 0.35
    early_stop_anti_delta: float = 0.08
    outcome_accept_value_delta: float = 0.08
    outcome_accept_trust_delta: float = 0.04
    outcome_dismiss_anti_delta: float = 0.04


_DEFAULT_EVENT_IMPULSES: dict[str, tuple[float, float, float, float, float]] = {
    "message_received": (0.03, 0.02, 0.01, 0.00, 0.00),
    "message_opened": (0.04, 0.02, 0.02, 0.01, 0.00),
    "ui_click": (0.03, 0.00, 0.01, 0.01, 0.00),
    "audio_started": (0.05, 0.03, 0.03, 0.02, 0.00),
    "audio_completed": (0.06, 0.04, 0.04, 0.02, 0.00),
    "audio_stopped": (-0.01, -0.01, 0.00, 0.00, 0.02),
    "offer_shown": (0.02, 0.00, 0.03, 0.01, 0.00),
    "paywall_opened": (0.03, 0.00, 0.04, 0.02, 0.00),
    "offer_outcome": (0.00, 0.00, 0.00, 0.00, 0.00),
}


@dataclass(frozen=True)
class ImpulseBoundsPolicy:
    """Canonical defaults for bounded behavioral impulse calculations.

    The policy is deliberately data-only: it does not make decisions and it does
    not create an alternate behavior engine. Decision-making remains owned by the
    canonical DecisionCore path.
    """

    zero_value: float = 0.0
    bounds: ImpulseBounds = field(default_factory=ImpulseBounds)
    event_impulses: dict[str, tuple[float, float, float, float, float]] = field(
        default_factory=lambda: dict(_DEFAULT_EVENT_IMPULSES)
    )


DEFAULT_IMPULSE_BOUNDS_POLICY = ImpulseBoundsPolicy()

__all__ = [
    "CANON_IMPULSE_BOUNDS_POLICY",
    "DEFAULT_IMPULSE_BOUNDS_POLICY",
    "ImpulseBounds",
    "ImpulseBoundsPolicy",
]
