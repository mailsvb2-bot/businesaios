from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_DOCUMENT_CONTRACT = True


class DocumentStatus(StrEnum):
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
class Document:
    """Stable business-document identity whose content lives in immutable Artifacts."""

    document_id: str
    tenant_id: str
    business_id: str
    artifact_id: str
    document_kind: str | None = None
    title: str | None = None
    revision: int = 1
    status: DocumentStatus = DocumentStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("document_id", "tenant_id", "business_id", "artifact_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "document_kind", _optional(self.document_kind, "document_kind", 100))
        object.__setattr__(self, "title", _optional(self.title, "title", 300))
        revision = int(self.revision)
        if revision < 1:
            raise ValueError("document revision must be >= 1")
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "status", DocumentStatus(self.status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("document timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.status is DocumentStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived document requires archived_at_ms")
        if self.status is DocumentStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active document cannot have archived_at_ms")


class DocumentNotFound(LookupError):
    pass


__all__ = ["CANON_DOCUMENT_CONTRACT", "Document", "DocumentNotFound", "DocumentStatus"]
