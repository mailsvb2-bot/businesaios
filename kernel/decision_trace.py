from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
import shared.types as _shared_types


@dataclass(frozen=True)
class DecisionTrace:
    request_id: str
    decision_id: str = field(default_factory=lambda: _shared_types.new_id('decision'))
    steps: List[str] = field(default_factory=list)
    created_at: object = field(default_factory=_shared_types.utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)
