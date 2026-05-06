from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRights:
    may_recommend: bool = False
    may_block: bool = False
    may_promote: bool = False
    may_publish: bool = False
    may_mutate_objective: bool = False


RIGHTS = {
    "decision_core": DecisionRights(may_block=True, may_promote=True),
    "evaluation": DecisionRights(may_recommend=True),
    "safety": DecisionRights(may_block=True),
    "training": DecisionRights(),
    "serving": DecisionRights(),
    "rollout": DecisionRights(),
    "config": DecisionRights(),
}


def assert_right(role: str, flag: str) -> bool:
    rights = RIGHTS[role]
    return bool(getattr(rights, flag))

__all__ = [
    "DecisionRights",
    "RIGHTS",
    "assert_right",
]
