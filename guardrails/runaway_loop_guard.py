from __future__ import annotations

from guardrails._shared import GuardCheckResult, _action_type, _as_int, _payload_view


class RunawayLoopGuard:
    def __init__(self, *, repetition_threshold: int = 3) -> None:
        self._repetition_threshold = max(2, int(repetition_threshold))

    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        action_type = _action_type(body)
        if not action_type:
            return GuardCheckResult(True, 'runaway_guard_not_applicable').as_tuple()
        repeats = _as_int(body.get('repeat_count', body.get('repeats', 0)), minimum=0)
        if repeats >= self._repetition_threshold:
            return GuardCheckResult(False, 'runaway_loop_detected').as_tuple()
        return GuardCheckResult(True, 'runaway_loop_clear').as_tuple()
