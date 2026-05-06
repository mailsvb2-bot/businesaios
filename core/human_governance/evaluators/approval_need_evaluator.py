from __future__ import annotations

from ..contracts import HumanGovernancePolicyContract
from ..types import ApprovalState, ReviewItem


class ApprovalNeedEvaluator:
    def __init__(self, policy: HumanGovernancePolicyContract) -> None:
        self._policy = policy

    def evaluate(self, review: ReviewItem, state: ApprovalState | None) -> bool:
        if state is None:
            return True
        return self._policy.needs_approval(state.status)
