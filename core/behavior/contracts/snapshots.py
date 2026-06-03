from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class PersonFieldSnapshot:
    snapshot_id: str
    entity_id: str
    created_at: datetime
    observables: Mapping[str, float]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrgFieldSnapshot:
    snapshot_id: str
    org_id: str
    created_at: datetime
    observables: Mapping[str, float]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SegmentFieldSnapshot:
    snapshot_id: str
    segment_id: str
    created_at: datetime
    observables: Mapping[str, float]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketFieldSnapshot:
    snapshot_id: str
    market_id: str
    created_at: datetime
    observables: Mapping[str, float]
    metadata: Mapping[str, Any] = field(default_factory=dict)
