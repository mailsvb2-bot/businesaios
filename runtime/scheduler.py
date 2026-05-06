from __future__ import annotations

"""Runtime scheduler jobs.

This file hosts the offline ML job that closes the learning ring:

events/rewards → dataset snapshot → offline train → validate → register → rollout → monitor → rollback

IMPORTANT:
- The job never deploys directly.
- Any deployment/rollback is requested via DecisionCore and executed via RuntimeExecutor.
- Feedback-loop guards must run at canonical train/evaluate/rollout boundaries.
"""

import time
from typing import Optional

from learning.replay import FeedbackLoopFirewall
from ml.policy_promotion_guard import PolicyPromotionGuard
from ml.policy_rollout_manager import PolicyRolloutManager
from runtime.autopilot_feedback_guard import AutopilotFeedbackGuard
from runtime.scheduler_parts.monitoring import (
    build_commit_metrics,
    load_candidate_metrics,
)
from runtime.scheduler_parts.result import LearningJobResult
from runtime.scheduler_monitoring_flow import evaluate_monitor_window
from runtime.scheduler_run_cycle import run_learning_cycle

CANON_RUNTIME_SCHEDULER_SINGLE_DECISION_PATH = True
CANON_RUNTIME_SCHEDULER_ORCHESTRATOR_ONLY = True



class LearningJob:
    def __init__(
        self,
        *,
        builder,
        trainer,
        validator,
        rollout,
        decision_core,
        executor,
        event_store,
        monitor_window_ms: int = 60_000,
        rollback_drop: float = 0.2,
        min_online_n: int = 20,
        auto_deploy_guard=None,
        feedback_loop_firewall: FeedbackLoopFirewall | None = None,
        policy_promotion_guard: PolicyPromotionGuard | None = None,
        policy_rollout_manager: PolicyRolloutManager | None = None,
        autopilot_feedback_guard: AutopilotFeedbackGuard | None = None,
        decision_input_provider: object | None = None,
    ) -> None:
        self._builder = builder
        self._trainer = trainer
        self._validator = validator
        self._rollout = rollout
        self._decision_core = decision_core
        self._executor = executor
        self._event_store = event_store
        self._monitor_window_ms = int(monitor_window_ms)
        self._rollback_drop = float(rollback_drop)
        self._min_online_n = int(min_online_n)
        self._auto_deploy_guard = auto_deploy_guard
        self._feedback_loop_firewall = feedback_loop_firewall or FeedbackLoopFirewall(min_eval_delay_ms=0)
        self._policy_promotion_guard = policy_promotion_guard or PolicyPromotionGuard(min_sample_size=1, min_improvement=0.0)
        self._policy_rollout_manager = policy_rollout_manager or PolicyRolloutManager(soak_period_ms=0)
        self._autopilot_feedback_guard = autopilot_feedback_guard or AutopilotFeedbackGuard()
        self._decision_input_provider = decision_input_provider
        self._active_rollout_id: str | None = None

    def _skip_result(self, reason: str, *, snapshot_id: str, model_id: str) -> LearningJobResult:
        return LearningJobResult(status="skip", snapshot_id=snapshot_id, model_id=model_id, reason=reason)

    def run_once(self) -> LearningJobResult:
        return run_learning_cycle(self)

    def monitor_and_maybe_rollback(self) -> Optional[LearningJobResult]:
        st = self._rollout.state()
        if st.status != "rolling" or not st.candidate_policy_id:
            return None

        now_ms = int(time.time() * 1000)
        candidate_metrics = load_candidate_metrics(
            event_store=self._event_store,
            candidate_policy_id=str(st.candidate_policy_id),
            window_ms=self._monitor_window_ms,
            now_ms=now_ms,
        )
        baseline_metrics = self._rollout.baseline_metrics()
        self._active_rollout_id, waiting_result = evaluate_monitor_window(
            decision_core=self._decision_core,
            executor=self._executor,
            rollout=self._rollout,
            policy_rollout_manager=self._policy_rollout_manager,
            active_rollout_id=self._active_rollout_id,
            now_ms=now_ms,
            baseline_metrics=baseline_metrics,
            candidate_metrics=candidate_metrics,
            rollback_drop=self._rollback_drop,
            min_online_n=self._min_online_n,
            on_cleanup_error_module=__name__,
            decision_input_provider=self._decision_input_provider,
        )
        if waiting_result is not None:
            return waiting_result

        base_reward = float(baseline_metrics.get("online_mean_reward", baseline_metrics.get("offline_mean_reward", 0.0)) or 0.0)
        base_ltv = float(baseline_metrics.get("online_mean_ltv", 0.0) or 0.0)
        self._rollout.commit(
            build_commit_metrics(
                baseline_metrics=baseline_metrics,
                base_reward=base_reward,
                base_ltv=base_ltv,
                candidate_metrics=candidate_metrics,
            )
        )
        return LearningJobResult(status="rollout_committed")