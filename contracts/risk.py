from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

RISK_SCHEMA_VERSION = 1
CANON_RISK_SEVERITY_CONTRACT = True
CANON_RISK_ENTITY_CONTRACT = True


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLifecycleStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class RiskNotFound(LookupError):
    pass

@dataclass(frozen=True)
class Risk:
    risk_id: str
    tenant_id: str
    business_id: str
    risk_type: str
    level: RiskLevel | str
    subject_kind: str | None = None
    subject_id: str | None = None
    schema_version: int = RISK_SCHEMA_VERSION
    lifecycle_status: RiskLifecycleStatus | str = RiskLifecycleStatus.OPEN
    created_at_ms: int = 0
    updated_at_ms: int = 0
    closed_at_ms: int | None = None

    def __post_init__(self) -> None:
        for name in ("risk_id", "tenant_id", "business_id", "risk_type"):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "level", RiskLevel(self.level))
        object.__setattr__(self, "lifecycle_status", RiskLifecycleStatus(self.lifecycle_status))
        kind = None if self.subject_kind is None else str(self.subject_kind).strip() or None
        subject_id = None if self.subject_id is None else str(self.subject_id).strip() or None
        if (kind is None) != (subject_id is None):
            raise ValueError("subject_kind and subject_id must be set together")
        object.__setattr__(self, "subject_kind", kind)
        object.__setattr__(self, "subject_id", subject_id)
        if isinstance(self.schema_version, bool) or int(self.schema_version) != RISK_SCHEMA_VERSION:
            raise ValueError("unsupported risk schema_version")
        object.__setattr__(self, "schema_version", RISK_SCHEMA_VERSION)
        created = int(self.created_at_ms)
        updated = int(self.updated_at_ms)
        if created < 0 or updated < 0 or updated < created:
            raise ValueError("risk timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        closed = self.closed_at_ms
        if closed is not None:
            closed = int(closed)
            if closed < updated:
                raise ValueError("closed_at_ms cannot precede updated_at_ms")
        if self.lifecycle_status is RiskLifecycleStatus.CLOSED and closed is None:
            raise ValueError("closed risk requires closed_at_ms")
        if self.lifecycle_status is RiskLifecycleStatus.OPEN and closed is not None:
            raise ValueError("open risk cannot have closed_at_ms")
        object.__setattr__(self, "closed_at_ms", closed)


__all__ = [
    "CANON_RISK_ENTITY_CONTRACT",
    "CANON_RISK_SEVERITY_CONTRACT",
    "RISK_SCHEMA_VERSION",
    "Risk",
    "RiskLevel",
    "RiskLifecycleStatus",
    "RiskNotFound",
]
