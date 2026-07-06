from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

CANON_SAFETY_OBSERVABILITY_CONTRACTS = True


@dataclass(frozen=True)
class SafetyEvent:
    tenant_id: str
    action: str
    stage: str
    status: str
    control: str = ''
    reason: str = ''
    details: Mapping[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


__all__ = ["CANON_SAFETY_OBSERVABILITY_CONTRACTS", "SafetyEvent"]
