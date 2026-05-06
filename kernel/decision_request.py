from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import shared.types as _shared_types


@dataclass(frozen=True)
class DecisionRequest:
    business_id: str
    objective: str
    input_bundle_id: str
    request_id: str = field(default_factory=lambda: _shared_types.new_id('request'))
    requested_at: object = field(default_factory=_shared_types.utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)
