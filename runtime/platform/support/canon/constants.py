from __future__ import annotations

from runtime.canon import CANONICAL_DECISION_CORE_MODULE

DECISION_AUTHORITY_PATH = CANONICAL_DECISION_CORE_MODULE
OPTIMIZATION_OBJECTIVE = "business_value_under_hard_safety_constraints"
PROMOTION_REQUIRES_EVALUATION = True
PROMOTION_REQUIRES_HUMAN_OVERRIDE_PATH = True
EXECUTION_FLOW = (
    "rollout",
    "dataset",
    "training",
    "evaluation",
    "promotion_gate",
    "serving",
)
FORBIDDEN_AUTHORITY_PATHS = (
    "platform.optimization",
    "platform.policy",
    "platform.serving",
)

__all__ = [
    "CANONICAL_DECISION_CORE_MODULE",
    "DECISION_AUTHORITY_PATH",
    "EXECUTION_FLOW",
    "FORBIDDEN_AUTHORITY_PATHS",
    "OPTIMIZATION_OBJECTIVE",
    "PROMOTION_REQUIRES_EVALUATION",
    "PROMOTION_REQUIRES_HUMAN_OVERRIDE_PATH",
]
