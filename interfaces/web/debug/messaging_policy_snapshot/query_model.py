from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotQuery:
    tenant_id: str
    user_id: str
    correlation_id: str
