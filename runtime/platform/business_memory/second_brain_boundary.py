from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CANON_BUSINESS_MEMORY_SECOND_BRAIN_BOUNDARY = True

_FORBIDDEN_TOP_LEVEL_KEYS = frozenset({
    'blocked_actions',
    'budget_envelope',
    'autonomy_tier',
    'operator_overrides',
    'goal_plan',
})

_FORBIDDEN_LEARNED_PREFERENCES_KEYS = frozenset({
    'preferred_action_types',
    'preferred_actions',
    'recommended_action_types',
    'suggested_next_actions',
    'next_actions',
    'next_action',
    'recommended_action',
})

_FORBIDDEN_OPERATING_CONSTRAINTS_KEYS = frozenset({
    'blocked_actions',
    'operator_handoff_actions',
    'autonomy_tier',
    'budget_envelope',
    'next_action',
    'recommended_action',
})

_FORBIDDEN_NESTED_KEYS = frozenset(
    set(_FORBIDDEN_TOP_LEVEL_KEYS)
    | set(_FORBIDDEN_LEARNED_PREFERENCES_KEYS)
    | set(_FORBIDDEN_OPERATING_CONSTRAINTS_KEYS)
)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _sanitize_nested(value: Any, *, forbidden: frozenset[str]) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, raw_item in dict(value).items():
            key = str(raw_key)
            if key.casefold() in forbidden:
                continue
            cleaned = _sanitize_nested(raw_item, forbidden=forbidden)
            if cleaned in ('', [], {}):
                continue
            result[key] = cleaned
        return result
    if _is_sequence(value):
        items: list[Any] = []
        for item in list(value):
            cleaned = _sanitize_nested(item, forbidden=forbidden)
            if cleaned in ('', [], {}):
                continue
            items.append(cleaned)
        return items
    return value


def _clean_mapping(value: Any, *, forbidden: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    cleaned = _sanitize_nested(dict(value), forbidden=forbidden)
    return dict(cleaned) if isinstance(cleaned, Mapping) else {}


def sanitize_business_memory_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Strip action-guiding fields from business-memory payloads.

    Business memory may provide evidence and audit state, but it must not expose
    fields that can silently evolve into a second decision path.
    """

    current = {
        str(key): value
        for key, value in dict(payload or {}).items()
        if str(key).casefold() not in _FORBIDDEN_TOP_LEVEL_KEYS
    }
    cleaned = _sanitize_nested(current, forbidden=_FORBIDDEN_NESTED_KEYS)
    if not isinstance(cleaned, Mapping):
        return {}
    current = dict(cleaned)
    if 'learned_preferences' in current:
        cleaned_preferences = _clean_mapping(
            current.get('learned_preferences'),
            forbidden=_FORBIDDEN_LEARNED_PREFERENCES_KEYS,
        )
        if cleaned_preferences:
            current['learned_preferences'] = cleaned_preferences
        else:
            current.pop('learned_preferences', None)
    if 'operating_constraints' in current:
        cleaned_constraints = _clean_mapping(
            current.get('operating_constraints'),
            forbidden=_FORBIDDEN_OPERATING_CONSTRAINTS_KEYS,
        )
        if cleaned_constraints:
            current['operating_constraints'] = cleaned_constraints
        else:
            current.pop('operating_constraints', None)
    return current


__all__ = ['CANON_BUSINESS_MEMORY_SECOND_BRAIN_BOUNDARY', 'sanitize_business_memory_payload']
