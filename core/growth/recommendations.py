from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class AdsObjectRef:
    platform: str
    account_id: str
    object_type: str
    object_id: str

@dataclass(frozen=True)
class AdsRecommendation:
    rec_id: str
    title: str
    rationale: str
    target: AdsObjectRef
    patch: dict[str, Any]
    expected_impact: dict[str, Any]
    risk_notes: str | None = None
