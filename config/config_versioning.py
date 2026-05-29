from __future__ import annotations

CANON_COMPAT_SHIM = True

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Mapping

from governance.persistence_codec import to_jsonable

CANON_CONFIG_VERSIONING = True


def utc_now() -> datetime:
    return datetime.now(UTC)


def _clean_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


@dataclass(frozen=True)
class ConfigVersion:
    namespace: str
    entity_id: str
    fingerprint: str
    revision: int = 1
    parent_fingerprint: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by: str = "system"
    change_reason: str = ""
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        _clean_text(self.namespace, field_name="namespace")
        _clean_text(self.entity_id, field_name="entity_id")
        _clean_text(self.fingerprint, field_name="fingerprint")
        if int(self.revision) < 1:
            raise ValueError("revision must be >= 1")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")

    @property
    def version_id(self) -> str:
        self.validate()
        return f"{self.namespace}:{self.entity_id}:{self.revision}:{self.fingerprint}"

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "namespace": self.namespace,
            "entity_id": self.entity_id,
            "fingerprint": self.fingerprint,
            "revision": int(self.revision),
            "parent_fingerprint": self.parent_fingerprint,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "created_by": str(self.created_by or "system").strip() or "system",
            "change_reason": str(self.change_reason or "").strip(),
            "labels": {str(k): str(v) for k, v in dict(self.labels).items()},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ConfigVersion:
        item = dict(payload or {})
        created_at_raw = str(item.get("created_at") or "").strip()
        created_at = datetime.fromisoformat(created_at_raw) if created_at_raw else utc_now()
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        version = cls(
            namespace=str(item.get("namespace") or "").strip(),
            entity_id=str(item.get("entity_id") or "").strip(),
            fingerprint=str(item.get("fingerprint") or "").strip(),
            revision=int(item.get("revision") or 1),
            parent_fingerprint=None if item.get("parent_fingerprint") is None else str(item.get("parent_fingerprint") or "").strip() or None,
            created_at=created_at,
            created_by=str(item.get("created_by") or "system").strip() or "system",
            change_reason=str(item.get("change_reason") or "").strip(),
            labels={str(k): str(v) for k, v in dict(item.get("labels") or {}).items()},
        )
        version.validate()
        return version


class ConfigVersioning:
    """Pure version stamping for configuration payloads.

    This module computes immutable version metadata only.
    It must not contain runtime decision logic or policy verdicts.
    """

    @staticmethod
    def canonical_payload(payload: Mapping[str, Any]) -> str:
        return json.dumps(
            to_jsonable(dict(payload)),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def fingerprint(cls, payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(cls.canonical_payload(payload).encode("utf-8")).hexdigest()

    @classmethod
    def is_semantically_same(
        cls,
        *,
        left_payload: Mapping[str, Any],
        right_payload: Mapping[str, Any],
    ) -> bool:
        return cls.fingerprint(left_payload) == cls.fingerprint(right_payload)

    @classmethod
    def next_revision(
        cls,
        *,
        payload: Mapping[str, Any],
        previous: ConfigVersion | None,
    ) -> int:
        if previous is None:
            return 1
        candidate_fingerprint = cls.fingerprint(payload)
        if candidate_fingerprint == previous.fingerprint:
            return int(previous.revision)
        return int(previous.revision) + 1

    @classmethod
    def create(
        cls,
        *,
        namespace: str,
        entity_id: str,
        payload: Mapping[str, Any],
        previous: ConfigVersion | None = None,
        created_by: str = "system",
        change_reason: str = "",
        labels: Mapping[str, str] | None = None,
    ) -> ConfigVersion:
        fingerprint = cls.fingerprint(payload)
        version = ConfigVersion(
            namespace=_clean_text(namespace, field_name="namespace"),
            entity_id=_clean_text(entity_id, field_name="entity_id"),
            fingerprint=fingerprint,
            revision=cls.next_revision(payload=payload, previous=previous),
            parent_fingerprint=None if previous is None else previous.fingerprint,
            created_by=str(created_by or "system").strip() or "system",
            change_reason=str(change_reason or "").strip(),
            labels={str(k): str(v) for k, v in dict(labels or {}).items()},
        )
        version.validate()
        return version


__all__ = [
    "CANON_CONFIG_VERSIONING",
    "ConfigVersion",
    "ConfigVersioning",
    "utc_now",
]
