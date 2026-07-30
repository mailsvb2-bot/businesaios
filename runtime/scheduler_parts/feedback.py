from __future__ import annotations

from typing import Any

from learning.replay import PolicyMetadata
from runtime.canon import CANONICAL_DECISION_CORE_MODULE

CANONICAL_LEARNING_RETRAINING_OWNER = "runtime.scheduler.LearningJob"
CANON_RUNTIME_SCHEDULER_FEEDBACK_SINGLE_OWNER = True


def component_identity(component: Any, *, fallback: str) -> str:
    """Return a stable identity for one injected pipeline component.

    The scheduler receives concrete trainer and validator objects from boot
    wiring. Their class identity is the authoritative owner marker; maintaining
    a parallel table of component names would create another brain and drift as
    implementations move.
    """

    cls = component.__class__ if component is not None else None
    module = str(getattr(cls, "__module__", "") or "").strip()
    qualname = str(getattr(cls, "__qualname__", "") or "").strip()
    if module and qualname:
        return f"{module}.{qualname}"
    return str(fallback)


def build_policy_metadata(
    *,
    policy_id: str,
    train_dataset_id: str,
    trained_at_ms: int,
    trainer_component: str,
) -> PolicyMetadata:
    return PolicyMetadata(
        policy_id=str(policy_id),
        trained_at_ms=int(trained_at_ms),
        source_dataset_id=str(train_dataset_id),
        trained_by_component=str(trainer_component),
    )


def guard_feedback_pipeline(
    *,
    feedback_loop_firewall,
    autopilot_feedback_guard,
    policy: PolicyMetadata,
    train_dataset_id: str,
    eval_dataset_id: str,
    now_ms: int,
    trainer_component: str,
    evaluator_component: str,
    retraining_origin: str = CANONICAL_LEARNING_RETRAINING_OWNER,
) -> None:
    feedback_loop_firewall.validate_all(
        policy=policy,
        train_dataset_id=train_dataset_id,
        eval_dataset_id=eval_dataset_id,
        trainer_component=str(trainer_component),
        evaluator_component=str(evaluator_component),
        now_ms=now_ms,
    )
    autopilot_feedback_guard.validate_full_chain(
        action_origin=CANONICAL_DECISION_CORE_MODULE,
        evaluation_origin=str(evaluator_component),
        retraining_origin=str(retraining_origin),
    )


__all__ = [
    "CANONICAL_LEARNING_RETRAINING_OWNER",
    "CANON_RUNTIME_SCHEDULER_FEEDBACK_SINGLE_OWNER",
    "build_policy_metadata",
    "component_identity",
    "guard_feedback_pipeline",
]
