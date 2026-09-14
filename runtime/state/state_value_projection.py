from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.state.state_contract import StateFieldRecord
from runtime.state.state_freshness_policy import NON_DECISION_FRESHNESS_STATUSES

STATE_VALUE_PROJECTION_DOES_NOT_OWN_STATE = True


def materialize_state_values(fields: Mapping[str, StateFieldRecord]) -> dict[str, Any]:
    """Build the decision-facing values view only from validated canonical fields."""
    root: dict[str, Any] = {}
    for field_path, record in fields.items():
        if record.freshness_status in NON_DECISION_FRESHNESS_STATUSES:
            continue
        target = root
        parts = [part for part in str(field_path).split(".") if part]
        if not parts:
            continue
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = record.value
    return root


__all__ = ["STATE_VALUE_PROJECTION_DOES_NOT_OWN_STATE", "materialize_state_values"]
