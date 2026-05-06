from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


CANON_MARKET_INTELLIGENCE_ADVANCED_MODELS = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def _safe_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


@dataclass(frozen=True)
class EntityCandidate:
    entity_id: str
    entity_kind: str
    title: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'entity_id', _text(self.entity_id))
        object.__setattr__(self, 'entity_kind', _text(self.entity_kind, default='unknown'))
        object.__setattr__(self, 'title', _text(self.title))
        aliases = tuple(str(item).strip() for item in self.aliases if str(item).strip())
        object.__setattr__(self, 'aliases', aliases)
        object.__setattr__(self, 'attributes', _safe_dict(self.attributes))


@dataclass(frozen=True)
class TrendPoint:
    tenant_id: str
    entity_id: str
    metric: str
    value: float
    observed_at: str = field(default_factory=lambda: _utc_now().isoformat())
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'tenant_id', _text(self.tenant_id, default='default'))
        object.__setattr__(self, 'entity_id', _text(self.entity_id))
        object.__setattr__(self, 'metric', _text(self.metric))
        object.__setattr__(self, 'value', float(self.value))
        object.__setattr__(self, 'observed_at', _text(self.observed_at, default=_utc_now().isoformat()))
        object.__setattr__(self, 'metadata', _safe_dict(self.metadata))


@dataclass(frozen=True)
class HumanFeedbackEvent:
    tenant_id: str
    entity_id: str
    label: str
    score_delta: float = 0.0
    is_false_positive: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)
    feedback_at: str = field(default_factory=lambda: _utc_now().isoformat())
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'tenant_id', _text(self.tenant_id, default='default'))
        object.__setattr__(self, 'entity_id', _text(self.entity_id))
        object.__setattr__(self, 'label', _text(self.label))
        object.__setattr__(self, 'score_delta', max(-1.0, min(float(self.score_delta), 1.0)))
        object.__setattr__(self, 'is_false_positive', bool(self.is_false_positive))
        tags = tuple(str(item).strip() for item in self.tags if str(item).strip())
        object.__setattr__(self, 'tags', tags)
        object.__setattr__(self, 'feedback_at', _text(self.feedback_at, default=_utc_now().isoformat()))
        object.__setattr__(self, 'metadata', _safe_dict(self.metadata))


__all__ = [
    'CANON_MARKET_INTELLIGENCE_ADVANCED_MODELS',
    'EntityCandidate',
    'TrendPoint',
    'HumanFeedbackEvent',
]
