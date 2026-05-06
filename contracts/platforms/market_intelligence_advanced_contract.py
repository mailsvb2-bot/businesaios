from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


CANON_MARKET_INTELLIGENCE_ADVANCED_CONTRACT = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def _safe_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _safe_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = _text(value)
    return (text,) if text else ()


@dataclass(frozen=True)
class ProviderCursor:
    tenant_id: str
    provider: str
    source_family: str
    scope_key: str
    cursor: str | None = None
    last_seen_at: str | None = None
    checksum: str | None = None
    updated_at: str = field(default_factory=lambda: _utc_now().isoformat())
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'tenant_id', _text(self.tenant_id, default='default'))
        object.__setattr__(self, 'provider', _text(self.provider))
        object.__setattr__(self, 'source_family', _text(self.source_family))
        object.__setattr__(self, 'scope_key', _text(self.scope_key, default='global'))
        object.__setattr__(self, 'cursor', _text(self.cursor) or None)
        object.__setattr__(self, 'last_seen_at', _text(self.last_seen_at) or None)
        object.__setattr__(self, 'checksum', _text(self.checksum) or None)
        object.__setattr__(self, 'updated_at', _text(self.updated_at, default=_utc_now().isoformat()))
        object.__setattr__(self, 'metadata', _safe_dict(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'provider': self.provider,
            'source_family': self.source_family,
            'scope_key': self.scope_key,
            'cursor': self.cursor,
            'last_seen_at': self.last_seen_at,
            'checksum': self.checksum,
            'updated_at': self.updated_at,
            'metadata': dict(self.metadata),
        }


@dataclass(frozen=True)
class UnifiedSignal:
    tenant_id: str
    entity_id: str
    entity_kind: str
    source_family: str
    provider: str
    signal_kind: str
    observed_at: str
    confidence: float = 0.0
    strength: float = 0.0
    freshness: float = 0.0
    frequency: float = 0.0
    tags: tuple[str, ...] = field(default_factory=tuple)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'tenant_id', _text(self.tenant_id, default='default'))
        object.__setattr__(self, 'entity_id', _text(self.entity_id))
        object.__setattr__(self, 'entity_kind', _text(self.entity_kind, default='unknown'))
        object.__setattr__(self, 'source_family', _text(self.source_family))
        object.__setattr__(self, 'provider', _text(self.provider))
        object.__setattr__(self, 'signal_kind', _text(self.signal_kind, default='generic'))
        object.__setattr__(self, 'observed_at', _text(self.observed_at, default=_utc_now().isoformat()))
        object.__setattr__(self, 'confidence', max(0.0, min(float(self.confidence), 1.0)))
        object.__setattr__(self, 'strength', max(0.0, min(float(self.strength), 1.0)))
        object.__setattr__(self, 'freshness', max(0.0, min(float(self.freshness), 1.0)))
        object.__setattr__(self, 'frequency', max(0.0, min(float(self.frequency), 1.0)))
        object.__setattr__(self, 'tags', _safe_tuple(self.tags))
        object.__setattr__(self, 'payload', _safe_dict(self.payload))

    def as_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'entity_id': self.entity_id,
            'entity_kind': self.entity_kind,
            'source_family': self.source_family,
            'provider': self.provider,
            'signal_kind': self.signal_kind,
            'observed_at': self.observed_at,
            'confidence': self.confidence,
            'strength': self.strength,
            'freshness': self.freshness,
            'frequency': self.frequency,
            'tags': list(self.tags),
            'payload': dict(self.payload),
        }


@dataclass(frozen=True)
class OpportunityEvidence:
    tenant_id: str
    opportunity_type: str
    entity_id: str
    title: str
    confidence: float
    support_signals: int
    rationale: tuple[str, ...] = field(default_factory=tuple)
    payload: Mapping[str, Any] = field(default_factory=dict)
    derived_at: str = field(default_factory=lambda: _utc_now().isoformat())

    def __post_init__(self) -> None:
        object.__setattr__(self, 'tenant_id', _text(self.tenant_id, default='default'))
        object.__setattr__(self, 'opportunity_type', _text(self.opportunity_type))
        object.__setattr__(self, 'entity_id', _text(self.entity_id))
        object.__setattr__(self, 'title', _text(self.title))
        object.__setattr__(self, 'confidence', max(0.0, min(float(self.confidence), 1.0)))
        object.__setattr__(self, 'support_signals', max(0, int(self.support_signals)))
        object.__setattr__(self, 'rationale', _safe_tuple(self.rationale))
        object.__setattr__(self, 'payload', _safe_dict(self.payload))
        object.__setattr__(self, 'derived_at', _text(self.derived_at, default=_utc_now().isoformat()))

    def as_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'opportunity_type': self.opportunity_type,
            'entity_id': self.entity_id,
            'title': self.title,
            'confidence': self.confidence,
            'support_signals': self.support_signals,
            'rationale': list(self.rationale),
            'payload': dict(self.payload),
            'derived_at': self.derived_at,
        }


__all__ = [
    'CANON_MARKET_INTELLIGENCE_ADVANCED_CONTRACT',
    'ProviderCursor',
    'UnifiedSignal',
    'OpportunityEvidence',
]
