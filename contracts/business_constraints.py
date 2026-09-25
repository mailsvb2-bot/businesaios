from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

BUSINESS_CONSTRAINT_SCHEMA_VERSION = 1
CANON_BUSINESS_CONSTRAINT_CONTRACT = True


class ConstraintSeverity(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class ConstraintLifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConstraintComparison(StrEnum):
    LTE = "lte"
    GTE = "gte"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int = 200) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class BusinessConstraint:
    """PII-free canonical business Constraint identity and lifecycle."""

    constraint_id: str
    tenant_id: str
    business_id: str
    constraint_kind: str
    severity: ConstraintSeverity = ConstraintSeverity.HARD
    subject_type: str | None = None
    subject_id: str | None = None
    state_key: str | None = None
    schema_version: int = BUSINESS_CONSTRAINT_SCHEMA_VERSION
    lifecycle_status: ConstraintLifecycleStatus = ConstraintLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None
    comparison: ConstraintComparison | None = None
    threshold: float | None = None

    def __post_init__(self) -> None:
        for field_name in ("constraint_id", "tenant_id", "business_id", "constraint_kind"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        subject_type = _optional(self.subject_type, "subject_type", 80)
        subject_id = _optional(self.subject_id, "subject_id")
        if (subject_type is None) != (subject_id is None):
            raise ValueError("subject_type and subject_id must be provided together")
        object.__setattr__(self, "subject_type", subject_type)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "state_key", _optional(self.state_key, "state_key", 160))
        object.__setattr__(self, "severity", ConstraintSeverity(self.severity))
        comparison = None if self.comparison is None else ConstraintComparison(self.comparison)
        threshold = self.threshold
        if comparison is None:
            if threshold is not None:
                raise ValueError("threshold requires comparison")
            object.__setattr__(self, "comparison", None)
            object.__setattr__(self, "threshold", None)
        else:
            if subject_type != "metric":
                raise ValueError("structured comparison requires subject_type=metric")
            if isinstance(threshold, bool) or threshold is None:
                raise ValueError("structured comparison requires finite threshold")
            try:
                threshold_number = float(threshold)
            except (TypeError, ValueError) as exc:
                raise ValueError("structured comparison requires finite threshold") from exc
            if not isfinite(threshold_number):
                raise ValueError("structured comparison requires finite threshold")
            object.__setattr__(self, "comparison", comparison)
            object.__setattr__(self, "threshold", threshold_number)
        if isinstance(self.schema_version, bool) or int(self.schema_version) != BUSINESS_CONSTRAINT_SCHEMA_VERSION:
            raise ValueError(f"unsupported business constraint schema_version: {self.schema_version}")
        object.__setattr__(self, "schema_version", BUSINESS_CONSTRAINT_SCHEMA_VERSION)
        object.__setattr__(self, "lifecycle_status", ConstraintLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("business constraint timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        archived = self.archived_at_ms
        if archived is not None:
            archived = int(archived)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.lifecycle_status is ConstraintLifecycleStatus.ACTIVE and archived is not None:
            raise ValueError("active constraint cannot have archived_at_ms")
        if self.lifecycle_status is ConstraintLifecycleStatus.ARCHIVED and archived is None:
            raise ValueError("archived constraint requires archived_at_ms")


class BusinessConstraintNotFound(LookupError):
    pass


__all__ = [
    "BUSINESS_CONSTRAINT_SCHEMA_VERSION",
    "CANON_BUSINESS_CONSTRAINT_CONTRACT",
    "BusinessConstraint",
    "BusinessConstraintNotFound",
    "ConstraintComparison",
    "ConstraintLifecycleStatus",
    "ConstraintSeverity",
]
