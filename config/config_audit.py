from __future__ import annotations

CANON_COMPAT_SHIM = True

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Mapping

from governance.persistence_codec import ensure_parent_dir, to_jsonable

CANON_CONFIG_AUDIT = True


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ConfigAuditEvent:
    namespace: str
    entity_id: str
    action: str
    actor: str = "system"
    tenant_id: str | None = None
    version_id: str | None = None
    correlation_id: str | None = None
    payload: Mapping[str, object] = field(default_factory=dict)
    emitted_at: datetime = field(default_factory=utc_now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> None:
        if not str(self.namespace or "").strip():
            raise ValueError("namespace is required")
        if not str(self.entity_id or "").strip():
            raise ValueError("entity_id is required")
        if not str(self.action or "").strip():
            raise ValueError("action is required")
        if not str(self.actor or "").strip():
            raise ValueError("actor is required")
        if not str(self.event_id or "").strip():
            raise ValueError("event_id is required")
        if self.emitted_at.tzinfo is None:
            raise ValueError("emitted_at must be timezone-aware")


class PersistentConfigAuditLog:
    """Append-only JSONL audit log with a tamper-evident hash chain."""

    def __init__(self, path: str | Path) -> None:
        self._path = ensure_parent_dir(Path(path))
        self._lock = RLock()
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: ConfigAuditEvent) -> None:
        event.validate()
        with self._lock:
            previous_hash = self._last_chain_hash_unlocked()
            payload = self._canonical_record(event)
            payload["previous_hash"] = previous_hash
            payload["record_hash"] = self._record_hash(payload)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                handle.write("\n")

    def read_events(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            if not self._path.exists():
                return ()
            rows: list[dict[str, object]] = []
            for line in self._path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text:
                    continue
                rows.append(json.loads(text))
            return tuple(rows)

    def validate_chain(self) -> None:
        previous_hash = "GENESIS"
        for row in self.read_events():
            stored_previous_hash = str(row.get("previous_hash") or "")
            stored_record_hash = str(row.get("record_hash") or "")
            if stored_previous_hash != previous_hash:
                raise ValueError("config audit chain previous_hash mismatch")
            candidate = dict(row)
            candidate.pop("record_hash", None)
            expected_hash = self._record_hash(candidate)
            if stored_record_hash != expected_hash:
                raise ValueError("config audit chain record_hash mismatch")
            previous_hash = stored_record_hash

    def _last_chain_hash_unlocked(self) -> str:
        if not self._path.exists():
            return "GENESIS"
        last_hash = "GENESIS"
        for line in self._path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            last_hash = str(row.get("record_hash") or "GENESIS")
        return last_hash

    @staticmethod
    def _record_hash(payload: Mapping[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _canonical_record(event: ConfigAuditEvent) -> dict[str, object]:
        return {
            "event_id": event.event_id,
            "namespace": event.namespace,
            "entity_id": event.entity_id,
            "tenant_id": event.tenant_id,
            "action": event.action,
            "actor": event.actor,
            "version_id": event.version_id,
            "correlation_id": event.correlation_id,
            "payload": to_jsonable(dict(event.payload)),
            "emitted_at": event.emitted_at.astimezone(UTC).isoformat(),
        }


__all__ = [
    "CANON_CONFIG_AUDIT",
    "ConfigAuditEvent",
    "PersistentConfigAuditLog",
    "utc_now",
]
