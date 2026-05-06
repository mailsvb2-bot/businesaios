from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_bool, _as_int, _payload_view


class MultiStepApproval:
    def __init__(self, *, min_approvals: int = 2) -> None:
        self._min_approvals = max(1, int(min_approvals))

    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        required = _as_bool(body.get('requires_multi_step_approval') or body.get('approval_required'))
        if not required:
            return GuardCheckResult(True, 'approval_not_required').as_tuple()
        approvals = body.get('approvals') or body.get('approval_chain') or ()
        count = len(tuple(approvals)) if not isinstance(approvals, str) else _as_int(approvals, default=0, minimum=0)
        if count < self._min_approvals:
            return GuardCheckResult(False, 'insufficient_approvals').as_tuple()
        return GuardCheckResult(True, 'approvals_satisfied').as_tuple()
