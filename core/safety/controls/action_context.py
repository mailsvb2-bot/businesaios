from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SafetyActionContext:
    action: str
    tenant_id: str
    user_id: str | None
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
