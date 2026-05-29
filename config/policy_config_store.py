from __future__ import annotations

CANON_COMPAT_SHIM = True

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from config.config_audit import ConfigAuditEvent, PersistentConfigAuditLog
from config.config_versioning import ConfigVersion, ConfigVersioning, utc_now
from core.tenancy.normalization import normalize_tenant_id
from governance.persistence_codec import atomic_write_json, read_json_or_default, to_jsonable

CANON_POLICY_CONFIG_STORE = True

_POLICY_NAMESPACE = "policy_config"


def _normalized_optional_tenant_id(value: str | None) -> str | None:
    normalized = normalize_tenant_id(value)
    return normalized or None


def _parse_datetime(value: object) -> datetime:
    text = str(value or "").strip()
    parsed = datetime.fromisoformat(text) if text else utc_now()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=utc_now().tzinfo)
    return parsed


@dataclass(frozen=True)
class PolicyConfigSnapshot:
    policy_name: str
    tenant_id: str | None = None
    scope: str = "global"
    config: Mapping[str, Any] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utc_now)
    version: ConfigVersion | None = None

    def validate(self) -> None:
        if not str(self.policy_name or "").strip():
            raise ValueError("policy_name is required")
        if not str(self.scope or "").strip():
            raise ValueError("scope is required")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        if self.version is not None:
            self.version.validate()

    def normalized(self) -> PolicyConfigSnapshot:
        return PolicyConfigSnapshot(
            policy_name=str(self.policy_name).strip(),
            tenant_id=_normalized_optional_tenant_id(self.tenant_id),
            scope=str(self.scope or "global").strip() or "global",
            config=to_jsonable(dict(self.config)),
            labels={str(k): str(v) for k, v in dict(self.labels).items()},
            updated_at=self.updated_at,
            version=self.version,
        )

    def entity_id(self) -> str:
        tenant_scope = self.tenant_id or "global"
        return f"{tenant_scope}:{str(self.scope).strip() or 'global'}:{str(self.policy_name).strip()}"

    def payload_for_versioning(self) -> dict[str, Any]:
        return {
            "policy_name": str(self.policy_name).strip(),
            "tenant_id": _normalized_optional_tenant_id(self.tenant_id),
            "scope": str(self.scope or "global").strip() or "global",
            "config": to_jsonable(dict(self.config)),
            "labels": {str(k): str(v) for k, v in dict(self.labels).items()},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> PolicyConfigSnapshot:
        item = dict(payload or {})
        version = None
        if isinstance(item.get("version"), Mapping):
            version = ConfigVersion.from_dict(dict(item.get("version") or {}))
        snapshot = cls(
            policy_name=str(item.get("policy_name") or "").strip(),
            tenant_id=_normalized_optional_tenant_id(item.get("tenant_id") if item.get("tenant_id") is None else str(item.get("tenant_id"))),
            scope=str(item.get("scope") or "global").strip() or "global",
            config=dict(item.get("config") or {}),
            labels={str(k): str(v) for k, v in dict(item.get("labels") or {}).items()},
            updated_at=_parse_datetime(item.get("updated_at")),
            version=version,
        ).normalized()
        snapshot.validate()
        return snapshot

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "policy_name": str(self.policy_name).strip(),
            "tenant_id": _normalized_optional_tenant_id(self.tenant_id),
            "scope": str(self.scope or "global").strip() or "global",
            "config": to_jsonable(dict(self.config)),
            "labels": {str(k): str(v) for k, v in dict(self.labels).items()},
            "updated_at": self.updated_at.isoformat(),
            "version": None if self.version is None else self.version.to_dict(),
        }


class InMemoryPolicyConfigStore:
    def __init__(self) -> None:
        self._snapshots: dict[str, PolicyConfigSnapshot] = {}
        self._history: dict[str, list[PolicyConfigSnapshot]] = {}
        self._lock = RLock()

    def get(self, *, policy_name: str, tenant_id: str | None = None, scope: str = "global") -> PolicyConfigSnapshot | None:
        with self._lock:
            return self._snapshots.get(self._key(policy_name=policy_name, tenant_id=tenant_id, scope=scope))

    def require(self, *, policy_name: str, tenant_id: str | None = None, scope: str = "global") -> PolicyConfigSnapshot:
        snapshot = self.get(policy_name=policy_name, tenant_id=tenant_id, scope=scope)
        if snapshot is None:
            raise KeyError(f"missing policy config: {policy_name}")
        return snapshot

    def list_all(self) -> tuple[PolicyConfigSnapshot, ...]:
        with self._lock:
            return tuple(sorted(self._snapshots.values(), key=lambda item: item.entity_id()))

    def save(
        self,
        snapshot: PolicyConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> PolicyConfigSnapshot:
        normalized = snapshot.normalized()
        normalized.validate()
        key = self._key(policy_name=normalized.policy_name, tenant_id=normalized.tenant_id, scope=normalized.scope)
        with self._lock:
            previous = self._snapshots.get(key)
            if previous is not None and expected_revision is not None and int(previous.version.revision if previous.version else 1) != int(expected_revision):
                raise RuntimeError("policy config optimistic concurrency check failed")
            next_version = ConfigVersioning.create(
                namespace=_POLICY_NAMESPACE,
                entity_id=normalized.entity_id(),
                payload=normalized.payload_for_versioning(),
                previous=None if previous is None else previous.version,
                created_by=actor,
                change_reason=reason,
                labels=normalized.labels,
            )
            if previous is not None and previous.version is not None and next_version.fingerprint == previous.version.fingerprint:
                return previous
            stored = PolicyConfigSnapshot(
                policy_name=normalized.policy_name,
                tenant_id=normalized.tenant_id,
                scope=normalized.scope,
                config=to_jsonable(dict(normalized.config)),
                labels={str(k): str(v) for k, v in dict(normalized.labels).items()},
                updated_at=utc_now(),
                version=next_version,
            )
            stored.validate()
            self._snapshots[key] = stored
            self._history.setdefault(key, []).append(stored)
            return stored

    def history(self, *, policy_name: str, tenant_id: str | None = None, scope: str = "global") -> tuple[PolicyConfigSnapshot, ...]:
        key = self._key(policy_name=policy_name, tenant_id=tenant_id, scope=scope)
        with self._lock:
            return tuple(self._history.get(key, ()))

    @staticmethod
    def _key(*, policy_name: str, tenant_id: str | None, scope: str) -> str:
        return f"{_normalized_optional_tenant_id(tenant_id) or 'global'}::{str(scope).strip() or 'global'}::{str(policy_name).strip()}"


class PersistentPolicyConfigStore(InMemoryPolicyConfigStore):
    def __init__(self, *, path: str | Path | None = None, audit_log_path: str | Path | None = None) -> None:
        super().__init__()
        self._path = Path(path) if path is not None else policy_config_store_path()
        self._audit_log = PersistentConfigAuditLog(
            Path(audit_log_path) if audit_log_path is not None else policy_config_audit_log_path()
        )
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def save(
        self,
        snapshot: PolicyConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> PolicyConfigSnapshot:
        before = self.get(policy_name=snapshot.policy_name, tenant_id=snapshot.tenant_id, scope=snapshot.scope)
        stored = super().save(snapshot, actor=actor, reason=reason, expected_revision=expected_revision)
        if before is stored:
            return stored
        self._flush()
        self._audit_log.append(
            ConfigAuditEvent(
                namespace=_POLICY_NAMESPACE,
                entity_id=stored.entity_id(),
                tenant_id=stored.tenant_id,
                action="upsert",
                actor=actor,
                version_id=None if stored.version is None else stored.version.version_id,
                payload={
                    "policy_name": stored.policy_name,
                    "scope": stored.scope,
                    "labels": dict(stored.labels),
                },
            )
        )
        return stored

    def _load(self) -> None:
        payload = read_json_or_default(self._path, default={"items": []})
        rows = dict(payload).get("items", []) if isinstance(payload, dict) else []
        for row in rows:
            snapshot = PolicyConfigSnapshot.from_dict(dict(row))
            key = self._key(policy_name=snapshot.policy_name, tenant_id=snapshot.tenant_id, scope=snapshot.scope)
            self._snapshots[key] = snapshot
            self._history.setdefault(key, []).append(snapshot)

    def _flush(self) -> None:
        atomic_write_json(self._path, {"items": [snapshot.to_dict() for snapshot in self.list_all()]})


def policy_config_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_POLICY_CONFIG_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "policy_config_store.json"


def policy_config_audit_log_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_POLICY_CONFIG_AUDIT_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "policy_config_audit.jsonl"


__all__ = [
    "CANON_POLICY_CONFIG_STORE",
    "InMemoryPolicyConfigStore",
    "PersistentPolicyConfigStore",
    "PolicyConfigSnapshot",
    "policy_config_audit_log_path",
    "policy_config_store_path",
]
