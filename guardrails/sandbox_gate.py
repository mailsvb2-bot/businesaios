from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_bool, _payload_view


class SandboxGate:
    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        requires_sandbox = _as_bool(body.get('requires_sandbox'))
        sandbox_active = _as_bool(body.get('sandbox_active') or body.get('is_sandbox'))
        if requires_sandbox and not sandbox_active:
            return GuardCheckResult(False, 'sandbox_required').as_tuple()
        return GuardCheckResult(True, 'sandbox_ok').as_tuple()
