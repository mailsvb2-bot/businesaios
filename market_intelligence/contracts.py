from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


_FORBIDDEN_KEYS = frozenset({
    'final_decision', 'winner', 'winning_creative', 'executor_command',
    'direct_action', 'approved_action', 'action_to_execute',
})


def _find_forbidden_keys(value: object) -> set[str]:
    """Find decision/execution keys anywhere in provider-controlled metadata."""
    found: set[str] = set()
    if isinstance(value, MappingABC):
        for key, nested in value.items():
            key_text = str(key).casefold()
            if key_text in _FORBIDDEN_KEYS:
                found.add(key_text)
            found.update(_find_forbidden_keys(nested))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            found.update(_find_forbidden_keys(nested))
    return found


@dataclass(frozen=True)
class EvidenceRef:
    provider_key: str
    source_kind: str
    source_id: str
    observed_at: datetime
    retrieved_at: datetime
    freshness_seconds: int | None = None
    metadata: MappingABC[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        overlap = _find_forbidden_keys(self.metadata)
        if overlap:
            raise ValueError(f'evidence metadata crosses decision boundary: {sorted(overlap)}')


@dataclass(frozen=True)
class SearchDemandObservation:
    tenant_id: str
    business_id: str
    query: str
    database: str
    search_volume: int | None
    cpc: float | None
    competition: float | None
    keyword_difficulty: float | None
    evidence: EvidenceRef


@dataclass(frozen=True)
class SearchVisibilityObservation:
    tenant_id: str
    business_id: str
    domain: str
    query: str
    database: str
    position: int | None
    traffic_percent: float | None
    url: str | None
    evidence: EvidenceRef


@dataclass(frozen=True)
class MarketIntelligenceSnapshot:
    provider_key: str
    generated_at: datetime
    demand: tuple[SearchDemandObservation, ...] = ()
    visibility: tuple[SearchVisibilityObservation, ...] = ()
    warnings: tuple[str, ...] = ()


@runtime_checkable
class MarketIntelligenceProvider(Protocol):
    provider_key: str

    def keyword_demand(
        self, *, tenant_id: str, business_id: str, queries: Sequence[str], database: str
    ) -> MarketIntelligenceSnapshot: ...

    def organic_visibility(
        self, *, tenant_id: str, business_id: str, domain: str, database: str, limit: int = 100
    ) -> MarketIntelligenceSnapshot: ...
