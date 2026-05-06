from __future__ import annotations

CANON_RUNTIME_SCHEDULER_DEPLOY_FLOW_GATEWAY_ONLY = True
CANON_RUNTIME_SCHEDULER_DEPLOY_FLOW_NO_RAW_DECISION_ISSUE = True


from runtime.observability.error_handling import swallow
from runtime.scheduler_parts.decision_request import request_scheduler_decision_execution
from runtime.scheduler_helpers import build_system_world_state, cleanup_rollout

from runtime.scheduler_parts.result import LearningJobResult


def apply_auto_deploy_guard(*, auto_deploy_guard, best_policy_id: str, rollout_pct: int, skip_result) -> int | LearningJobResult:
    pct = int(rollout_pct)
    if auto_deploy_guard is None:
        return pct
    verdict = auto_deploy_guard.allow(
        {"kind": "deploy", "candidate_policy_id": best_policy_id, "rollout_pct": pct}
    )
    if not verdict.ok:
        return skip_result(f"autodeploy_guard:{verdict.reason}")
    return int(verdict.rollout_pct or pct)


def begin_rollout(*, policy_rollout_manager, baseline_state, best_policy_id: str, rollout_pct: int, now_ms: int, rollout_id: str) -> None:
    policy_rollout_manager.start_rollout(
        rollout_id=rollout_id,
        baseline_policy_id=str(baseline_state.active_policy_id),
        candidate_policy_id=best_policy_id,
        traffic_fraction=max(0.01, min(1.0, float(rollout_pct) / 100.0)),
        now_ms=now_ms,
    )


def request_rollout_execution(
    *,
    decision_core,
    executor,
    policy_rollout_manager,
    rollout,
    auto_deploy_guard,
    best_policy_id: str,
    rollout_pct: int,
    now_ms: int,
    rollout_id: str,
    on_cleanup_error_module: str,
    decision_input_provider=None,
):
    rollout.begin_rollout(best_policy_id, rollout_pct)
    ws = build_system_world_state(
        now_ms=now_ms,
        safe_mode=False,
        proposal={"kind": "deploy", "candidate_policy_id": best_policy_id, "rollout_pct": rollout_pct},
    )
    res = request_scheduler_decision_execution(
        issuer=decision_core,
        executor=executor,
        world_state=ws,
        proposal={"kind": "deploy", "candidate_policy_id": best_policy_id, "rollout_pct": rollout_pct},
        generated_at_ms=int(now_ms),
        safe_mode=False,
        decision_input_provider=decision_input_provider,
    )
    if not res.ok:
        try:
            cleanup_rollout(policy_rollout_manager, rollout_id)
        except Exception:
            swallow(on_cleanup_error_module, "runtime/scheduler.py")
        return LearningJobResult(status="deploy_failed", reason="executor_failed")

    if auto_deploy_guard is not None:
        try:
            auto_deploy_guard.note_deploy_executed()
        except Exception:
            swallow(on_cleanup_error_module, "runtime/scheduler.py")

    return LearningJobResult(status="deploy_requested", decision_id=res.decision_id)