from __future__ import annotations

from typing import Any

from config.live_canary_policy import (
    DEFAULT_LIVE_CANARY_POLICY,
    LiveCanaryPolicy,
)
from runtime.experiments.live_canary import LiveCanaryCoordinator
from runtime.experiments.outcome_observer import (
    LiveCanaryOutcomeObserver,
    LiveCanaryOutcomeSupervisor,
)


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
    observer = LiveCanaryOutcomeObserver(coordinator)
    supervisor = LiveCanaryOutcomeSupervisor(
        observer,
        interval_seconds=policy.outcome_poll_seconds,
    )
    core._live_canary = coordinator
    core._live_canary_outcome_observer = observer
    core._live_canary_outcome_supervisor = supervisor
    return coordinator


def start_live_canary_runtime(core: Any) -> None:
    supervisor = getattr(core, "_live_canary_outcome_supervisor", None)
    if supervisor is None:
        raise RuntimeError("LIVE_CANARY_OUTCOME_SUPERVISOR_REQUIRED")
    supervisor.start()


def detach_live_canary(core: Any) -> None:
    supervisor = getattr(core, "_live_canary_outcome_supervisor", None)
    if supervisor is not None:
        supervisor.request_stop()
        supervisor.join()
    core._live_canary = None
    core._live_canary_outcome_observer = None
    core._live_canary_outcome_supervisor = None


__all__ = [
    "attach_live_canary",
    "detach_live_canary",
    "start_live_canary_runtime",
]
