from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

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
    patch: Dict[str, Any]
    expected_impact: Dict[str, Any]
    risk_notes: Optional[str] = None
