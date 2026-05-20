from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class DemandChannel(str, Enum):
    GOOGLE_MAPS = "google_maps"
    SEARCH_ADS = "search_ads"
    MARKETPLACE = "marketplace"
    SOCIAL = "social"
    ORGANIC_CONTENT = "organic_content"
    PROGRAMMATIC = "programmatic"


class DemandSignalKind(str, Enum):
    SEARCH_INTENT = "search_intent"
    REVIEW_SIGNAL = "review_signal"
    LISTING_SIGNAL = "listing_signal"
    CONTENT_SIGNAL = "content_signal"
    COMPETITOR_SIGNAL = "competitor_signal"


class CandidateWriteMode(str, Enum):
    ADVISORY_ONLY = "advisory_only"


@dataclass(frozen=True)
class DemandSignal:
    signal_id: str
    tenant_id: str
    kind: DemandSignalKind
    channel: DemandChannel
    observed_at: datetime
    source_ref: str
    normalized_text: str
    confidence: float
    raw_fingerprint: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DemandCandidate:
    candidate_id: str
    tenant_id: str
    channel: DemandChannel
    signal_ids: tuple[str, ...]
    write_mode: CandidateWriteMode
    evidence_refs: tuple[str, ...]
    created_at: datetime
    payload: Mapping[str, Any]
    idempotency_key: str
    correlation_id: str
