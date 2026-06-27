from __future__ import annotations

from runtime.observability.error_handling import swallow
from runtime.scheduler_helpers import build_system_world_state, cleanup_rollout
from runtime.scheduler_parts.decision_request import request_scheduler_decision_execution
from runtime.scheduler_parts.result import LearningJobResult

CANON_RUNTIME_SCHEDULER_MONITORING_GATEWAY_ONLY = True
CANON_RUNTIME_SCHEDULER_MONITORING_NO_RAW_DECISION_ISSUE = True


def load_candidate_metrics(*, event_store, candidate_policy_id: str, window_ms: int, now_ms: int):
    from ml.metrics import compute_online_metrics

    events = event_store.load(now_ms - window_ms, now_ms)
    return compute_online_metrics(events, policy_id=candidate_policy_id)


def maybe_request_rollback(
    *,
    decision_core,
    executor,
    rollout,
    policy_rollout_manager,
    active_rollout_id: str | None,
    now_ms: int,
    reason: str,
    on_cleanup_error_module: str,
    decision_input_provider=None,
):
    ws = build_system_world_state(
        now_ms=now_ms,
        safe_mode=True,
        proposal={"kind": "rollback", "reason": reason},
    )
    res = request_scheduler_decision_execution(
        issuer=decision_core,
        executor=executor,
        world_state=ws,
        proposal={"kind": "rollback", "reason": reason},
        generated_at_ms=int(now_ms),
        safe_mode=True,
        decision_input_provider=decision_input_provider,
    )
    rollout.rollback()
    next_rollout_id = active_rollout_id
    if active_rollout_id is not None:
        try:
            next_rollout_id = cleanup_rollout(policy_rollout_manager, active_rollout_id)
        except Exception:
            swallow(on_cleanup_error_module, "runtime/scheduler.py")
        next_rollout_id = None
    return next_rollout_id, LearningJobResult(status="rollback_requested", decision_id=res.decision_id)


def maybe_promote_rollout(*, policy_rollout_manager, active_rollout_id: str | None, now_ms: int, on_cleanup_error_module: str):
    if active_rollout_id is None:
        return None, None
    from ml.policy_rollout_manager import RolloutGuardViolation

    try:
        policy_rollout_manager.promote(active_rollout_id, now_ms=now_ms)
    except RolloutGuardViolation:
        return active_rollout_id, LearningJobResult(status="monitor_wait", reason="soak_period_not_finished")
    try:
        active_rollout_id = cleanup_rollout(policy_rollout_manager, active_rollout_id)
    except Exception:
        swallow(on_cleanup_error_module, "runtime/scheduler.py")
    return None, None


def build_commit_metrics(*, baseline_metrics: dict, base_reward: float, base_ltv: float, candidate_metrics):
    return {
        **baseline_metrics,
        "online_mean_reward": float(max(base_reward, candidate_metrics.mean_reward)),
        "online_mean_ltv": float(max(base_ltv, candidate_metrics.mean_ltv)),
        "online_n": float(candidate_metrics.n),
    }
