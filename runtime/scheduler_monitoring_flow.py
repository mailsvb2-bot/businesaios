from __future__ import annotations

from typing import Any

from runtime.scheduler_parts.monitoring import maybe_promote_rollout, maybe_request_rollback
from runtime.scheduler_parts.result import LearningJobResult
from runtime.scheduler_thresholds import compute_thresholds

CANON_RUNTIME_SCHEDULER_MONITORING_FLOW_SINGLE_PATH = True
CANON_RUNTIME_SCHEDULER_MONITORING_FLOW_GATEWAY_ONLY = True


def evaluate_monitor_window(
    *,
    decision_core,
    executor,
    rollout,
    policy_rollout_manager,
    active_rollout_id: str | None,
    now_ms: int,
    baseline_metrics: dict[str, Any],
    candidate_metrics: Any,
    rollback_drop: float,
    min_online_n: int,
    on_cleanup_error_module: str,
    decision_input_provider=None,
) -> tuple[str | None, LearningJobResult | None]:
    base_reward = float(baseline_metrics.get("online_mean_reward", baseline_metrics.get("offline_mean_reward", 0.0)) or 0.0)
    base_ltv = float(baseline_metrics.get("online_mean_ltv", 0.0) or 0.0)

    if candidate_metrics.n < min_online_n:
        return active_rollout_id, LearningJobResult(status="monitor_wait", reason=f"too_few_online_samples:{candidate_metrics.n}")

    reward_threshold, ltv_threshold = compute_thresholds(
        base_reward=base_reward,
        base_ltv=base_ltv,
        rollback_drop=rollback_drop,
    )
    if base_reward > 0.0 and candidate_metrics.mean_reward < reward_threshold:
        return maybe_request_rollback(
            decision_core=decision_core,
            executor=executor,
            rollout=rollout,
            policy_rollout_manager=policy_rollout_manager,
            active_rollout_id=active_rollout_id,
            now_ms=now_ms,
            reason="monitor_regression",
            on_cleanup_error_module=on_cleanup_error_module,
            decision_input_provider=decision_input_provider,
        )

    if base_ltv > 0.0 and candidate_metrics.mean_ltv < ltv_threshold:
        return maybe_request_rollback(
            decision_core=decision_core,
            executor=executor,
            rollout=rollout,
            policy_rollout_manager=policy_rollout_manager,
            active_rollout_id=active_rollout_id,
            now_ms=now_ms,
            reason="ltv_drop",
            on_cleanup_error_module=on_cleanup_error_module,
            decision_input_provider=decision_input_provider,
        )

    return maybe_promote_rollout(
        policy_rollout_manager=policy_rollout_manager,
        active_rollout_id=active_rollout_id,
        now_ms=now_ms,
        on_cleanup_error_module=on_cleanup_error_module,
    )
