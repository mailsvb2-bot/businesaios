from __future__ import annotations

from typing import Any

from config.live_canary_policy import (
    DEFAULT_LIVE_CANARY_POLICY,
    LiveCanaryPolicy,
)
from runtime.experiments.live_canary import LiveCanaryCoordinator


def attach_live_canary(
    core: Any,
    *,
    policy_registry: Any,
    candidate_policy_id: str,
    policy: LiveCanaryPolicy = DEFAULT_LIVE_CANARY_POLICY,
) -> LiveCanaryCoordinator:
    """Attach the sole live-canary coordinator to DecisionCore."""

    coordinator = LiveCanaryCoordinator(
        event_log=core._events,
        policy_registry=policy_registry,
        candidate_policy_id=str(candidate_policy_id),
        policy=policy,
    )
    core._live_canary = coordinator
    return coordinator


def detach_live_canary(core: Any) -> None:
    core._live_canary = None


__all__ = ["attach_live_canary", "detach_live_canary"]
