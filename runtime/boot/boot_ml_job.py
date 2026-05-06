from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""Offline ML job assembly for the boot pipeline.

Responsibility: construct the LearningJob (OfflineTrainer + RolloutManager +
AutoDeployGuard + …) from env config and already-wired objects.

Single public function: build_ml_job()
"""

from pathlib import Path
from typing import Any

from runtime.platform.app_paths import runtime_data_dir
from runtime.platform.config.env_flags import env_path
from ml.dataset_builder import DatasetBuilder as MLDatasetBuilder
from ml.event_store import RuntimeEventStoreAdapter
from learning.registry import ArtifactRegistry
from learning.trainer import OfflineTrainer as MLOfflineTrainer
from learning.trainer import PolicyValidatorV14
from ml.rollout_manager import RolloutManager
from ml.policy_promotion_guard import PolicyPromotionGuard
from ml.policy_rollout_manager import PolicyRolloutManager
from learning.replay import FeedbackLoopFirewall
from runtime.autopilot_feedback_guard import AutopilotFeedbackGuard
from runtime.boot.env import env_float, env_int
from runtime.boot.ml_job_defaults import (
    DEFAULT_ML_MIN_EVAL_DELAY_MS,
    DEFAULT_ML_MIN_IMPROVEMENT,
    DEFAULT_ML_MIN_ONLINE_N,
    DEFAULT_ML_MIN_SAMPLE_SIZE,
    DEFAULT_ML_MONITOR_WINDOW_MS,
    DEFAULT_ML_ROLLBACK_DROP,
    DEFAULT_ML_SOAK_PERIOD_MS,
)
from runtime.governance.auto_deploy_guard import build_auto_deploy_guard_from_env
from runtime.scheduler import LearningJob


def build_ml_job(
    *,
    event_store: Any,
    core: Any,
    executor: Any,
    policy_registry: Any,
    base: Path,
) -> LearningJob:
    """Construct and return the offline ML LearningJob."""
    ml_snapshots_dir = Path(str(env_path("ML_SNAPSHOTS_DIR", str(runtime_data_dir() / "ml_snapshots"))))

    ml_event_store = RuntimeEventStoreAdapter(event_store)
    artifact_registry = ArtifactRegistry()

    min_n = env_int("ML_MIN_N", DEFAULT_ML_MIN_SAMPLE_SIZE, lo=1, hi=1_000_000)
    min_improvement = env_float("ML_MIN_IMPROVEMENT", DEFAULT_ML_MIN_IMPROVEMENT, lo=0.0, hi=1.0)
    soak_period_ms = env_int(
        "ML_SOAK_PERIOD_MS",
        DEFAULT_ML_SOAK_PERIOD_MS,
        lo=0,
        hi=7 * 24 * 60 * 60 * 1000,
    )

    ml_builder = MLDatasetBuilder(ml_event_store, out_dir=ml_snapshots_dir)
    ml_trainer = MLOfflineTrainer(artifact_registry)
    ml_validator = PolicyValidatorV14(
        min_improvement=min_improvement,
        min_n=min_n,
    )
    rollout_mgr = RolloutManager(
        initial_policy_id=policy_registry.active_ref().policy_id
    )
    auto_deploy_guard = build_auto_deploy_guard_from_env()

    return LearningJob(
        builder=ml_builder,
        trainer=ml_trainer,
        validator=ml_validator,
        rollout=rollout_mgr,
        decision_core=core,
        executor=executor,
        event_store=ml_event_store,
        monitor_window_ms=env_int(
            "ML_MONITOR_WINDOW_MS",
            DEFAULT_ML_MONITOR_WINDOW_MS,
            lo=1_000,
            hi=24 * 60 * 60 * 1000,
        ),
        rollback_drop=env_float(
            "ML_ROLLBACK_DROP",
            DEFAULT_ML_ROLLBACK_DROP,
            lo=0.0,
            hi=1.0,
        ),
        min_online_n=env_int(
            "ML_MIN_ONLINE_N",
            DEFAULT_ML_MIN_ONLINE_N,
            lo=1,
            hi=1_000_000,
        ),
        auto_deploy_guard=auto_deploy_guard,
        feedback_loop_firewall=FeedbackLoopFirewall(
            min_eval_delay_ms=env_int(
                "ML_MIN_EVAL_DELAY_MS",
                DEFAULT_ML_MIN_EVAL_DELAY_MS,
                lo=0,
                hi=7 * 24 * 60 * 60 * 1000,
            )
        ),
        policy_promotion_guard=PolicyPromotionGuard(
            min_sample_size=min_n,
            min_improvement=min_improvement,
        ),
        policy_rollout_manager=PolicyRolloutManager(soak_period_ms=soak_period_ms),
        autopilot_feedback_guard=AutopilotFeedbackGuard(),
    )
