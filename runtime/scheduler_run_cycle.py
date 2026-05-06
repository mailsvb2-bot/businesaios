from __future__ import annotations

import time

from learning.replay import FeedbackLoopViolation
from ml.policy_promotion_guard import PromotionBlocked
from ml.policy_rollout_manager import RolloutGuardViolation
from runtime.autopilot_feedback_guard import AutopilotFeedbackGuardViolation
from runtime.scheduler_helpers import build_baseline_evaluation, build_candidate_evaluation
from runtime.scheduler_parts.baseline_refresh import refresh_baseline_metrics
from runtime.scheduler_parts.deploy_flow import (
    apply_auto_deploy_guard,
    begin_rollout,
    request_rollout_execution,
)
from runtime.scheduler_parts.feedback import build_policy_metadata, guard_feedback_pipeline
from runtime.scheduler_parts.result import LearningJobResult

CANON_RUNTIME_SCHEDULER_RUN_CYCLE_ORCHESTRATOR_ONLY = True
CANON_RUNTIME_SCHEDULER_RUN_CYCLE_NO_RAW_DECISION_ISSUE = True


def run_learning_cycle(job) -> LearningJobResult:
    """Run one guarded learning cycle for the canonical LearningJob.

    Kept outside runtime.scheduler so the public job class stays an orchestrator
    rather than turning into a second decision-like blob.
    """
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 7 * 24 * 3600 * 1000

    refresh_baseline_metrics(
        rollout=job._rollout,
        event_store=job._event_store,
        start_ms=start_ms,
        now_ms=now_ms,
    )

    snapshot = job._builder.build(start_ms, now_ms)
    train = job._trainer.train(snapshot)
    snapshot_id = str(snapshot.snapshot_id)
    model_id = str(train.model.model_id)
    best_policy_id = str(train.model.payload.get("best_policy_id") or "")
    if not best_policy_id:
        return job._skip_result("no_candidate", snapshot_id=snapshot_id, model_id=model_id)

    train_dataset_id = f"{snapshot_id}:train"
    eval_dataset_id = f"{snapshot_id}:eval"
    policy_meta = build_policy_metadata(
        policy_id=best_policy_id,
        train_dataset_id=train_dataset_id,
        trained_at_ms=now_ms,
    )

    try:
        guard_feedback_pipeline(
            feedback_loop_firewall=job._feedback_loop_firewall,
            autopilot_feedback_guard=job._autopilot_feedback_guard,
            policy=policy_meta,
            train_dataset_id=train_dataset_id,
            eval_dataset_id=eval_dataset_id,
            now_ms=now_ms,
        )
    except (FeedbackLoopViolation, AutopilotFeedbackGuardViolation) as exc:
        return job._skip_result(f"feedback_guard:{exc.__class__.__name__}", snapshot_id=snapshot_id, model_id=model_id)

    verdict = job._validator.validate(train.model, baseline_metrics=job._rollout.baseline_metrics())
    if not verdict.ok:
        return job._skip_result(str(verdict.reason), snapshot_id=snapshot_id, model_id=model_id)

    baseline_state = job._rollout.state()
    baseline_metrics = job._rollout.baseline_metrics()
    baseline_eval = build_baseline_evaluation(state=baseline_state, metrics=baseline_metrics)
    candidate_eval = build_candidate_evaluation(policy_id=best_policy_id, train_metrics=train.model.metrics)
    try:
        job._policy_promotion_guard.require_allowed(baseline_eval, candidate_eval)
    except PromotionBlocked as exc:
        return job._skip_result(f"promotion_guard:{exc.__class__.__name__}", snapshot_id=snapshot_id, model_id=model_id)

    rollout_pct = apply_auto_deploy_guard(
        auto_deploy_guard=job._auto_deploy_guard,
        best_policy_id=best_policy_id,
        rollout_pct=int(verdict.safe_rollout_pct),
        skip_result=lambda reason: job._skip_result(reason, snapshot_id=snapshot_id, model_id=model_id),
    )
    if isinstance(rollout_pct, LearningJobResult):
        return rollout_pct

    rollout_id = f"{model_id}:{best_policy_id}"
    try:
        begin_rollout(
            policy_rollout_manager=job._policy_rollout_manager,
            baseline_state=baseline_state,
            best_policy_id=best_policy_id,
            rollout_pct=int(rollout_pct),
            now_ms=now_ms,
            rollout_id=rollout_id,
        )
    except RolloutGuardViolation as exc:
        return job._skip_result(f"rollout_guard:{exc.__class__.__name__}", snapshot_id=snapshot_id, model_id=model_id)

    job._active_rollout_id = rollout_id
    result = request_rollout_execution(
        decision_core=job._decision_core,
        executor=job._executor,
        policy_rollout_manager=job._policy_rollout_manager,
        rollout=job._rollout,
        auto_deploy_guard=job._auto_deploy_guard,
        best_policy_id=best_policy_id,
        rollout_pct=int(rollout_pct),
        now_ms=now_ms,
        rollout_id=rollout_id,
        on_cleanup_error_module="runtime.scheduler",
        decision_input_provider=job._decision_input_provider,
    )
    if result.status == "deploy_failed":
        job._active_rollout_id = None
        return LearningJobResult(
            status=result.status,
            snapshot_id=snapshot_id,
            model_id=model_id,
            reason=result.reason,
        )
    return LearningJobResult(
        status=result.status,
        snapshot_id=snapshot_id,
        model_id=model_id,
        decision_id=result.decision_id,
    )
