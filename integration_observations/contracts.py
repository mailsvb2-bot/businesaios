from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import datetime


FORBIDDEN_OBSERVATION_KEYS = frozenset({
    'finaldecision', 'winner', 'winningcreative', 'executorcommand',
    'directaction', 'approvedaction', 'actiontoexecute',
})


def _normalized_observation_key(key: object) -> str:
    return ''.join(ch for ch in str(key).casefold() if ch.isalnum())


def _find_forbidden_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, MappingABC):
        for key, nested in value.items():
            key_text = _normalized_observation_key(key)
            if key_text in FORBIDDEN_OBSERVATION_KEYS:
                found.add(key_text)
            found.update(_find_forbidden_keys(nested))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            found.update(_find_forbidden_keys(nested))
    return found


@dataclass(frozen=True)
class ProviderObservationEnvelope:
    tenant_id: str
    business_id: str
    provider_key: str
    observation_type: str
    observed_at: datetime
    payload: MappingABC[str, object]
    evidence_ids: tuple[str, ...] = ()
    schema_version: str = '1'
    metadata: MappingABC[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        forbidden = _find_forbidden_keys(self.payload) | _find_forbidden_keys(self.metadata)
        if forbidden:
            raise ValueError(f'observation crosses canonical decision boundary: {sorted(forbidden)}')
