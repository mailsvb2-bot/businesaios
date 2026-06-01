from __future__ import annotations

from learning.replay import PolicyMetadata
from runtime.canon import CANONICAL_DECISION_CORE_MODULE


def build_policy_metadata(*, policy_id: str, train_dataset_id: str, trained_at_ms: int) -> PolicyMetadata:
    return PolicyMetadata(
        policy_id=str(policy_id),
        trained_at_ms=int(trained_at_ms),
        source_dataset_id=str(train_dataset_id),
        trained_by_component="learning.trainer",
    )


def guard_feedback_pipeline(
    *,
    feedback_loop_firewall,
    autopilot_feedback_guard,
    policy: PolicyMetadata,
    train_dataset_id: str,
    eval_dataset_id: str,
    now_ms: int,
) -> None:
    feedback_loop_firewall.validate_all(
        policy=policy,
        train_dataset_id=train_dataset_id,
        eval_dataset_id=eval_dataset_id,
        trainer_component="learning.trainer",
        evaluator_component="learning.trainer",
        now_ms=now_ms,
    )
    autopilot_feedback_guard.validate_full_chain(
        action_origin=CANONICAL_DECISION_CORE_MODULE,
        evaluation_origin="learning.trainer",
        retraining_origin="learning.trainer",
    )
