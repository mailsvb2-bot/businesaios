from __future__ import annotations

from typing import Any

from runtime.state.state_contract import (
    ABSENT_VALUE_KIND,
    CONFLICT_VALUE_KIND,
    STALE_VALUE_KIND,
    UNKNOWN_VALUE_KIND,
)

CANON_STATE_UNKNOWN_SEMANTICS = True


def classify_value_kind(
    *,
    value: Any,
    unknown: bool = False,
    absent: bool = False,
    stale: bool = False,
    conflict: bool = False,
) -> str:
    if conflict:
        return CONFLICT_VALUE_KIND
    if stale:
        return STALE_VALUE_KIND
    if absent:
        return ABSENT_VALUE_KIND
    if unknown:
        return UNKNOWN_VALUE_KIND
    return "known"


def is_unknown_marker(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"unknown", "n/a", "na", "not_available", "unavailable", "pending"}
    if isinstance(value, dict):
        return bool(value.get("unknown") is True)
    return False


def normalize_unknown(*, value: Any, unknown: bool = False, absent: bool = False) -> tuple[Any, bool, bool]:
    if absent:
        return None, False, True
    if unknown or is_unknown_marker(value):
        return None, True, False
    return value, False, False
