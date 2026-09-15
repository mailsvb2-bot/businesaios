from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

CANON_ARTIFACT_CONTRACT = True
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ArtifactStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class Artifact:
    """Canonical metadata identity for immutable business artifacts.

    Binary/content storage remains external. This entity stores only the scoped
    identity, an opaque storage reference, integrity metadata and lifecycle.
    """

    artifact_id: str
    tenant_id: str
    business_id: str
    artifact_kind: str | None = None
    storage_ref: str | None = None
    content_sha256: str | None = None
    media_type: str | None = None
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("artifact_id", "tenant_id", "business_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "artifact_kind", _optional(self.artifact_kind, "artifact_kind", 100))
        object.__setattr__(self, "storage_ref", _optional(self.storage_ref, "storage_ref", 500))
        object.__setattr__(self, "media_type", _optional(self.media_type, "media_type", 200))
        digest = _optional(self.content_sha256, "content_sha256", 64)
        if digest is not None and _SHA256_RE.fullmatch(digest) is None:
            raise ValueError("content_sha256 must be a 64-character hexadecimal digest")
        object.__setattr__(self, "content_sha256", None if digest is None else digest.lower())
        object.__setattr__(self, "status", ArtifactStatus(self.status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("artifact timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.status is ArtifactStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived artifact requires archived_at_ms")
        if self.status is ArtifactStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active artifact cannot have archived_at_ms")


class ArtifactNotFound(LookupError):
    pass


__all__ = ["Artifact", "ArtifactNotFound", "ArtifactStatus", "CANON_ARTIFACT_CONTRACT"]
