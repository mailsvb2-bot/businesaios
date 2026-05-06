from __future__ import annotations

from runtime.platform.support.common import new_id


def new_candidate_id() -> str:
    return new_id("candidate")


def new_rollout_id() -> str:
    return new_id("rollout")

__all__ = [
    "new_candidate_id",
    "new_rollout_id",
]
