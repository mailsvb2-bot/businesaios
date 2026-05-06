from __future__ import annotations

from typing import Any, Mapping


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


class UnsafeBudgetJumpGuard:
    def __init__(self, max_delta: float = 0.2) -> None:
        self._max_delta = max(0.0, float(max_delta))

    def _budget_delta(self, payload: Mapping[str, Any]) -> float:
        if 'budget_delta' in payload:
            return abs(_safe_float(payload.get('budget_delta')))
        old_budget = _safe_float(payload.get('previous_budget', payload.get('current_budget')), default=0.0)
        new_budget = _safe_float(payload.get('new_budget', old_budget), default=old_budget)
        return abs(new_budget - old_budget)

    def check(self, payload: dict) -> tuple[bool, str]:
        body = dict(payload or {})
        budget_delta = self._budget_delta(body)
        if budget_delta > self._max_delta:
            return False, 'unsafe_budget_jump'
        return True, 'ok'
