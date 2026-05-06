from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from governance.control_plane_audit_log import GovernanceAuditEvent, GovernanceAuditLogContract, NullGovernanceAuditLog
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from governance.persistence_paths import kill_switch_store_path


CANON_GOVERNANCE_KILL_SWITCH_REGISTRY = True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class KillSwitchEntry:
    switch_id: str
    scope: str
    scope_id: str
    reason: str
    activated_by: str
    activated_at: datetime
    expires_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.switch_id or "").strip():
            raise ValueError("switch_id is required")
        if not str(self.scope or "").strip():
            raise ValueError("scope is required")
        if not str(self.scope_id or "").strip():
            raise ValueError("scope_id is required")
        if not str(self.reason or "").strip():
            raise ValueError("reason is required")
        if not str(self.activated_by or "").strip():
            raise ValueError("activated_by is required")
        if self.expires_at is not None and self.expires_at <= self.activated_at:
            raise ValueError("expires_at must be greater than activated_at")


class KillSwitchRegistry:
    """
    Scope conventions:
    - global / "__all__"
    - tenant / "<tenant_id>"
    - action / "<action_name>"
    - category / "<action_category>"
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], KillSwitchEntry] = {}

    def activate(self, entry: KillSwitchEntry) -> None:
        entry.validate()
        self._entries[(entry.scope, entry.scope_id)] = entry

    def release(self, *, scope: str, scope_id: str) -> None:
        self._entries.pop((str(scope), str(scope_id)), None)

    def get(self, *, scope: str, scope_id: str) -> KillSwitchEntry | None:
        entry = self._entries.get((str(scope), str(scope_id)))
        if entry is None:
            return None
        if entry.expires_at is not None and _utc_now() >= entry.expires_at.astimezone(timezone.utc):
            self.release(scope=scope, scope_id=scope_id)
            return None
        return entry

    def find_blocker(
        self,
        *,
        tenant_id: str,
        action_name: str,
        action_category: str | None,
    ) -> KillSwitchEntry | None:
        for scope, scope_id in (
            ("global", "__all__"),
            ("tenant", str(tenant_id)),
            ("action", str(action_name)),
            ("category", str(action_category or "")),
        ):
            entry = self.get(scope=scope, scope_id=scope_id)
            if entry is not None:
                return entry
        return None


class PersistentKillSwitchRegistry(KillSwitchRegistry):
    """Durable kill-switch registry backed by a plain JSON snapshot."""

    def __init__(
        self,
        path: str | Path | None = None,
        audit_log: GovernanceAuditLogContract | None = None,
    ) -> None:
        self._path = Path(path) if path is not None else kill_switch_store_path()
        self._audit_log = audit_log or NullGovernanceAuditLog()
        super().__init__()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def activate(self, entry: KillSwitchEntry) -> None:
        super().activate(entry)
        self._flush()
        self._emit_audit(
            event_type="kill_switch_activated",
            tenant_id=str(entry.metadata.get("tenant_id") or "global"),
            payload={
                "switch_id": entry.switch_id,
                "scope": entry.scope,
                "scope_id": entry.scope_id,
                "reason": entry.reason,
                "activated_by": entry.activated_by,
            },
        )

    def release(self, *, scope: str, scope_id: str) -> None:
        existing = self._entries.get((str(scope), str(scope_id)))
        super().release(scope=scope, scope_id=scope_id)
        self._flush()
        if existing is not None:
            self._emit_audit(
                event_type="kill_switch_released",
                tenant_id=str(existing.metadata.get("tenant_id") or "global"),
                payload={
                    "switch_id": existing.switch_id,
                    "scope": existing.scope,
                    "scope_id": existing.scope_id,
                },
            )

    def get(self, *, scope: str, scope_id: str) -> KillSwitchEntry | None:
        entry = super().get(scope=scope, scope_id=scope_id)
        if (scope, scope_id) not in self._entries and entry is None:
            self._flush()
        return entry

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"entries": []})
        entries = raw.get("entries", []) if isinstance(raw, dict) else []
        loaded: dict[tuple[str, str], KillSwitchEntry] = {}
        for item in entries:
            entry = from_dataclass(KillSwitchEntry, item)
            loaded[(entry.scope, entry.scope_id)] = entry
        self._entries = loaded

    def _flush(self) -> None:
        atomic_write_json(
            self._path,
            {"entries": [to_jsonable(item) for item in self._entries.values()]},
        )

    def _emit_audit(self, *, event_type: str, tenant_id: str, payload: dict[str, object]) -> None:
        self._audit_log.append(
            GovernanceAuditEvent(
                event_type=event_type,
                tenant_id=str(tenant_id or "global"),
                emitted_at=_utc_now(),
                payload=payload,
            )
        )


__all__ = [
    "CANON_GOVERNANCE_KILL_SWITCH_REGISTRY",
    "KillSwitchEntry",
    "KillSwitchRegistry",
    "PersistentKillSwitchRegistry",
    "_utc_now",
]
