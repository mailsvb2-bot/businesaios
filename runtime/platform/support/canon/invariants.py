from __future__ import annotations

from runtime.platform.support.canon.constants import EXECUTION_FLOW
from runtime.platform.support.canon.decision_rights import RIGHTS
from runtime.platform.support.canon.module_boundaries import BOUNDARIES

INVARIANTS = (
    "exactly_one_decision_core",
    "evaluation_precedes_promotion",
    "training_cannot_publish",
    "serving_cannot_promote",
    "reward_cannot_redefine_objective",
    "rollout_collects_only",
)


def validate_invariant_name(name: str) -> bool:
    return name in INVARIANTS


def validate_execution_flow(flow: tuple[str, ...] | None = None) -> bool:
    return tuple(flow or EXECUTION_FLOW) == EXECUTION_FLOW


def validate_decision_sovereignty() -> bool:
    promoted_roles = [name for name, rights in RIGHTS.items() if rights.may_promote]
    return promoted_roles == ["decision_core"]


def validate_boundaries() -> bool:
    return (
        BOUNDARIES["training"]["can_publish"] is False
        and BOUNDARIES["serving"]["can_promote"] is False
        and BOUNDARIES["rollout"]["can_promote"] is False
    )

__all__ = [
    "BOUNDARIES",
    "EXECUTION_FLOW",
    "INVARIANTS",
    "RIGHTS",
    "validate_boundaries",
    "validate_decision_sovereignty",
    "validate_execution_flow",
    "validate_invariant_name",
]
