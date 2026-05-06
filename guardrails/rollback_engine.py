from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_bool, _payload_view


class RollbackEngine:
    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        rollback_requested = _as_bool(body.get('rollback_required') or body.get('rollback_requested'))
        unsafe = _as_bool(body.get('unsafe') or body.get('degraded'))
        if rollback_requested or unsafe:
            return GuardCheckResult(False, 'rollback_required').as_tuple()
        return GuardCheckResult(True, 'rollback_not_required').as_tuple()
