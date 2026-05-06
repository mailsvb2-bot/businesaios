from __future__ import annotations

"""Append-only audit log for governance control-plane events.

This module stores immutable event records only.
It must not contain decision logic or policy evaluation.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Mapping, Protocol

from governance.control_plane_audit_support import (
    approval_audit_lifecycle_counts,
    canonical_record,
    read_jsonl_events,
    safe_dict,
    sha256_hex,
    text,
    utc_now,
)
from governance.persistence_codec import ensure_parent_dir
from governance.persistence_paths import control_plane_audit_log_path


CANON_GOVERNANCE_CONTROL_PLANE_AUDIT_LOG = True


@dataclass(frozen=True)
class GovernanceAuditEvent:
    event_type: str
    tenant_id: str
    emitted_at: datetime = field(default_factory=utc_now)
    payload: Mapping[str, object] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> None:
        if not str(self.event_type or "").strip():
            raise ValueError("event_type is required")
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.event_id or "").strip():
            raise ValueError("event_id is required")
        if self.emitted_at.tzinfo is None:
            raise ValueError("emitted_at must be timezone-aware")


class GovernanceAuditLogContract(Protocol):
    def append(self, event: GovernanceAuditEvent) -> None: ...
    def read_events(self) -> tuple[dict[str, object], ...]: ...
    def read_tenant_events(self, tenant_id: str, *, limit: int | None = None) -> tuple[dict[str, object], ...]: ...
    def summarize_tenant_lifecycle(self, tenant_id: str, *, limit: int | None = None) -> dict[str, object]: ...
    def integrity_summary(self) -> dict[str, object]: ...


class NullGovernanceAuditLog(GovernanceAuditLogContract):
    def append(self, event: GovernanceAuditEvent) -> None:
        event.validate()
        return None

    def read_events(self) -> tuple[dict[str, object], ...]:
        return ()

    def read_tenant_events(self, tenant_id: str, *, limit: int | None = None) -> tuple[dict[str, object], ...]:
        return ()

    def summarize_tenant_lifecycle(self, tenant_id: str, *, limit: int | None = None) -> dict[str, object]:
        return {
            "tenant_id": text(tenant_id),
            "count": 0,
            "lifecycle_counts": approval_audit_lifecycle_counts(()),
            "recent_events": (),
            "integrity": self.integrity_summary(),
        }

    def integrity_summary(self) -> dict[str, object]:
        return {
            "checked": True,
            "valid": True,
            "event_count": 0,
            "chain_head": "GENESIS",
            "error": None,
        }


class PersistentGovernanceAuditLog(GovernanceAuditLogContract):
    """Plain JSONL append-only audit log for governance events.

    Each record includes a hash chain so tampering becomes detectable even
    though the storage backend remains file-based JSONL.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else control_plane_audit_log_path()
        ensure_parent_dir(self._path)
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: GovernanceAuditEvent) -> None:
        event.validate()
        payload = canonical_record(
            event_id=event.event_id,
            event_type=event.event_type,
            tenant_id=event.tenant_id,
            emitted_at=event.emitted_at,
            payload=event.payload,
        )
        previous_hash = self._last_chain_hash()
        record_for_hash = dict(payload)
        record_for_hash["previous_hash"] = previous_hash
        record_hash = sha256_hex(json.dumps(record_for_hash, ensure_ascii=False, sort_keys=True))
        payload["previous_hash"] = previous_hash
        payload["record_hash"] = record_hash
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            fh.write("\n")

    def read_events(self) -> tuple[dict[str, object], ...]:
        return read_jsonl_events(self._path)

    def read_tenant_events(self, tenant_id: str, *, limit: int | None = None) -> tuple[dict[str, object], ...]:
        normalized_tenant_id = text(tenant_id)
        if not normalized_tenant_id:
            return ()
        events = tuple(item for item in self.read_events() if text(item.get("tenant_id")) == normalized_tenant_id)
        if limit is not None and limit >= 0:
            return events[-int(limit):]
        return events

    def summarize_tenant_lifecycle(self, tenant_id: str, *, limit: int | None = None) -> dict[str, object]:
        events = self.read_tenant_events(tenant_id, limit=limit)
        recent_events = tuple(
            {
                "event_type": text(item.get("event_type")) or None,
                "emitted_at": text(item.get("emitted_at")) or None,
                "payload": safe_dict(item.get("payload")),
            }
            for item in events[-10:]
        )
        return {
            "tenant_id": text(tenant_id),
            "count": len(events),
            "lifecycle_counts": approval_audit_lifecycle_counts(events),
            "recent_events": recent_events,
            "integrity": self.integrity_summary(),
        }

    def integrity_summary(self) -> dict[str, object]:
        events = self.read_events()
        chain_head = str(events[-1].get("record_hash") or "GENESIS") if events else "GENESIS"
        try:
            self.validate_chain()
            return {
                "checked": True,
                "valid": True,
                "event_count": len(events),
                "chain_head": chain_head,
                "error": None,
            }
        except Exception as exc:
            return {
                "checked": True,
                "valid": False,
                "event_count": len(events),
                "chain_head": chain_head,
                "error": str(exc),
            }

    def validate_chain(self) -> None:
        previous_hash = "GENESIS"
        for item in self.read_events():
            stored_previous = str(item.get("previous_hash") or "")
            stored_hash = str(item.get("record_hash") or "")
            if stored_previous != previous_hash:
                raise ValueError("governance audit chain previous_hash mismatch")
            hash_input = dict(item)
            hash_input.pop("record_hash", None)
            expected_hash = sha256_hex(json.dumps(hash_input, ensure_ascii=False, sort_keys=True))
            if stored_hash != expected_hash:
                raise ValueError("governance audit chain record_hash mismatch")
            previous_hash = stored_hash

    def _last_chain_hash(self) -> str:
        events = self.read_events()
        if not events:
            return "GENESIS"
        return str(events[-1].get("record_hash") or "GENESIS")


__all__ = [
    "CANON_GOVERNANCE_CONTROL_PLANE_AUDIT_LOG",
    "GovernanceAuditEvent",
    "GovernanceAuditLogContract",
    "NullGovernanceAuditLog",
    "PersistentGovernanceAuditLog",
]
