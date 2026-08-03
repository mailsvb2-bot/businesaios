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
from runtime.experiments.watchdog import (
    LiveCanaryWatchdog,
    LiveCanaryWatchdogSupervisor,
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
    core._live_canary_watchdog = None
    core._live_canary_watchdog_supervisor = None
    core._live_canary_rollback_submitter = None
    return coordinator


def start_live_canary_runtime(core: Any) -> None:
    supervisor = getattr(core, "_live_canary_outcome_supervisor", None)
    if supervisor is None:
        raise RuntimeError("LIVE_CANARY_OUTCOME_SUPERVISOR_REQUIRED")
    supervisor.start()


def bind_live_canary_executor(core: Any, executor: Any) -> None:
    """Start immediate rollback supervision through RuntimeExecutor."""

    coordinator = getattr(core, "_live_canary", None)
    if coordinator is None:
        return
    if getattr(executor, "_decision_core", None) is not core:
        raise RuntimeError("LIVE_CANARY_EXECUTOR_CORE_MISMATCH")
    submit = getattr(executor, "submit_live_canary_rollback", None)
    if not callable(submit):
        raise RuntimeError("LIVE_CANARY_EXECUTOR_ROLLBACK_GATEWAY_REQUIRED")
    tenant_ids = tuple(coordinator.policy.allowed_tenant_ids)
    if len(tenant_ids) != 1:
        raise RuntimeError("LIVE_CANARY_SINGLE_TENANT_REQUIRED")

    def rollback_submitter(**kwargs: Any) -> None:
        submit(**kwargs)

    watchdog = LiveCanaryWatchdog(
        coordinator,
        tenant_id=tenant_ids[0],
        rollback_submitter=rollback_submitter,
        interval_seconds=max(1.0, coordinator.policy.outcome_poll_seconds),
    )
    supervisor = LiveCanaryWatchdogSupervisor(watchdog)
    core._live_canary_watchdog = watchdog
    core._live_canary_watchdog_supervisor = supervisor
    core._live_canary_rollback_submitter = rollback_submitter
    executor._live_canary_watchdog = watchdog
    executor._live_canary_watchdog_supervisor = supervisor
    executor._live_canary_rollback_submitter = rollback_submitter
    supervisor.start()


def detach_live_canary(core: Any) -> None:
    watchdog_supervisor = getattr(
        core,
        "_live_canary_watchdog_supervisor",
        None,
    )
    if watchdog_supervisor is not None:
        watchdog_supervisor.request_stop()
        watchdog_supervisor.join()
    outcome_supervisor = getattr(core, "_live_canary_outcome_supervisor", None)
    if outcome_supervisor is not None:
        outcome_supervisor.request_stop()
        outcome_supervisor.join()
    core._live_canary = None
    core._live_canary_outcome_observer = None
    core._live_canary_outcome_supervisor = None
    core._live_canary_watchdog = None
    core._live_canary_watchdog_supervisor = None
    core._live_canary_rollback_submitter = None


__all__ = [
    "attach_live_canary",
    "bind_live_canary_executor",
    "detach_live_canary",
    "start_live_canary_runtime",
]
