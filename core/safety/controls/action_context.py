from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class SafetyActionContext:
    action: str
    tenant_id: str
    user_id: str | None
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
