from __future__ import annotations

"""Canonical owner for tiny platform-support schemas and validators."""

from collections.abc import Mapping
from typing import Any

_SCHEMA_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    'checkpoint': ('uri',),
    'episode': ('trajectory',),
    'evaluation': ('candidate_id', 'metrics'),
    'experiment': ('experiment_id',),
    'incident': ('incident_type', 'description'),
    'policy': ('name', 'version'),
    'reward': ('value',),
    'rollout': ('rollout_id', 'episodes'),
    'trajectory': ('transitions',),
    'transition': ('observation', 'action', 'reward', 'done'),
}


def schema_for(name: str) -> dict[str, Any]:
    required = _SCHEMA_REQUIRED_FIELDS[name]
    return {'type': 'object', 'required': list(required)}


def is_valid_payload(name: str, payload: Mapping[str, Any] | object) -> bool:
    return isinstance(payload, Mapping) and all(field in payload for field in _SCHEMA_REQUIRED_FIELDS[name])


def schema_names() -> tuple[str, ...]:
    return tuple(_SCHEMA_REQUIRED_FIELDS)


__all__ = ['schema_for', 'is_valid_payload', 'schema_names']
