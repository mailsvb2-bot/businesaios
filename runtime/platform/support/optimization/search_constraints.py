from __future__ import annotations

import math
from typing import Any
from collections.abc import Mapping


class SearchConstraints:
    """Lightweight validation for local optimization/search payloads.

    This is intentionally a bounded validator, not a second planner. It only
    checks whether the support-layer constraints payload is structurally sane.
    """

    _POSITIVE_INT_KEYS = frozenset({"iterations", "population_size", "parallelism", "beam_width"})
    _NON_NEGATIVE_FLOAT_KEYS = frozenset({"budget", "cost_limit", "time_limit_seconds"})

    def valid(self, config: Mapping[str, Any] | object) -> bool:
        if not isinstance(config, Mapping):
            return False

        body = dict(config)
        if not body:
            return True

        for key in self._POSITIVE_INT_KEYS:
            if key in body and not self._positive_int(body.get(key)):
                return False

        for key in self._NON_NEGATIVE_FLOAT_KEYS:
            if key in body and not self._non_negative_float(body.get(key)):
                return False

        min_score = body.get("min_score")
        max_score = body.get("max_score")
        if min_score is not None or max_score is not None:
            if not self._finite_float(min_score, default=0.0):
                return False
            if not self._finite_float(max_score, default=1.0):
                return False
            if float(min_score if min_score is not None else 0.0) > float(max_score if max_score is not None else 1.0):
                return False

        return True

    @staticmethod
    def _positive_int(value: object) -> bool:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return False
        return parsed > 0

    @staticmethod
    def _non_negative_float(value: object) -> bool:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(parsed) and parsed >= 0.0

    @staticmethod
    def _finite_float(value: object, *, default: float) -> bool:
        try:
            parsed = default if value is None else float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(parsed)

__all__ = [
    "SearchConstraints",
]
