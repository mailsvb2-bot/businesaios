from __future__ import annotations


from runtime.canon import CANONICAL_DECISION_CORE_MODULE

ARCHITECTURE_NAME = "BUSINESAIOS RL Support Constitution"

DECISION_SOVEREIGN = CANONICAL_DECISION_CORE_MODULE
ALLOWED_AUTHORITY_ROLES = frozenset({"measure", "evaluate", "recommend", "block"})


def describe_constitution() -> dict[str, object]:
    return {
        "architecture_name": ARCHITECTURE_NAME,
        "decision_sovereign": DECISION_SOVEREIGN,
        "authority_roles": sorted(ALLOWED_AUTHORITY_ROLES),
    }

__all__ = [
    "ALLOWED_AUTHORITY_ROLES",
    "ARCHITECTURE_NAME",
    "CANONICAL_DECISION_CORE_MODULE",
    "DECISION_SOVEREIGN",
    "describe_constitution",
]
