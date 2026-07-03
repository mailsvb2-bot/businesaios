from __future__ import annotations


import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from config.config_audit import ConfigAuditEvent, PersistentConfigAuditLog
from config.config_versioning import ConfigVersion, ConfigVersioning, utc_now
from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import atomic_write_json, read_json_or_default, to_jsonable

CANON_COMPAT_SHIM = True

CANON_TENANT_CONFIG_STORE = True

_TENANT_NAMESPACE = "tenant_config"


def _parse_datetime(value: object) -> datetime:
    text = str(value or "").strip()
    parsed = datetime.fromisoformat(text) if text else utc_now()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=utc_now().tzinfo)
    return parsed


@dataclass(frozen=True)
class TenantConfigSnapshot:
    tenant_id: str
    runtime_overrides: Mapping[str, Any] = field(default_factory=dict)
    policy_overrides: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    feature_flags: Mapping[str, bool] = field(default_factory=dict)
    feature_variants: Mapping[str, str] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utc_now)
    version: ConfigVersion | None = None

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        for key in self.feature_flags:
            if not str(key or "").strip():
                raise ValueError("feature_flags keys must be non-empty")
        for key in self.feature_variants:
            if not str(key or "").strip():
                raise ValueError("feature_variants keys must be non-empty")
        for key in self.policy_overrides:
            if not str(key or "").strip():
                raise ValueError("policy_overrides keys must be non-empty")
        if self.version is not None:
            self.version.validate()

    def normalized(self) -> TenantConfigSnapshot:
        return TenantConfigSnapshot(
            tenant_id=require_tenant_id(self.tenant_id),
            runtime_overrides=to_jsonable(dict(self.runtime_overrides)),
            policy_overrides={str(k): to_jsonable(dict(v)) for k, v in dict(self.policy_overrides).items()},
            feature_flags={str(k): bool(v) for k, v in dict(self.feature_flags).items()},
            feature_variants={str(k): str(v) for k, v in dict(self.feature_variants).items()},
            labels={str(k): str(v) for k, v in dict(self.labels).items()},
            updated_at=self.updated_at,
            version=self.version,
        )

    def entity_id(self) -> str:
        return require_tenant_id(self.tenant_id)

    def payload_for_versioning(self) -> dict[str, Any]:
        return {
            "tenant_id": require_tenant_id(self.tenant_id),
            "runtime_overrides": to_jsonable(dict(self.runtime_overrides)),
            "policy_overrides": {str(k): to_jsonable(dict(v)) for k, v in dict(self.policy_overrides).items()},
            "feature_flags": {str(k): bool(v) for k, v in dict(self.feature_flags).items()},
            "feature_variants": {str(k): str(v) for k, v in dict(self.feature_variants).items()},
            "labels": {str(k): str(v) for k, v in dict(self.labels).items()},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> TenantConfigSnapshot:
        item = dict(payload or {})
        version = None
        if isinstance(item.get("version"), Mapping):
            version = ConfigVersion.from_dict(dict(item.get("version") or {}))
        snapshot = cls(
            tenant_id=require_tenant_id(item.get("tenant_id")),
            runtime_overrides=dict(item.get("runtime_overrides") or {}),
            policy_overrides={str(k): dict(v) for k, v in dict(item.get("policy_overrides") or {}).items()},
            feature_flags={str(k): bool(v) for k, v in dict(item.get("feature_flags") or {}).items()},
            feature_variants={str(k): str(v) for k, v in dict(item.get("feature_variants") or {}).items()},
            labels={str(k): str(v) for k, v in dict(item.get("labels") or {}).items()},
            updated_at=_parse_datetime(item.get("updated_at")),
            version=version,
        ).normalized()
        snapshot.validate()
        return snapshot

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "tenant_id": require_tenant_id(self.tenant_id),
            "runtime_overrides": to_jsonable(dict(self.runtime_overrides)),
            "policy_overrides": {str(k): to_jsonable(dict(v)) for k, v in dict(self.policy_overrides).items()},
            "feature_flags": {str(k): bool(v) for k, v in dict(self.feature_flags).items()},
            "feature_variants": {str(k): str(v) for k, v in dict(self.feature_variants).items()},
            "labels": {str(k): str(v) for k, v in dict(self.labels).items()},
            "updated_at": self.updated_at.isoformat(),
            "version": None if self.version is None else self.version.to_dict(),
        }


class InMemoryTenantConfigStore:
    def __init__(self) -> None:
        self._snapshots: dict[str, TenantConfigSnapshot] = {}
        self._history: dict[str, list[TenantConfigSnapshot]] = {}
        self._lock = RLock()

    def get(self, tenant_id: str) -> TenantConfigSnapshot | None:
        with self._lock:
            return self._snapshots.get(require_tenant_id(tenant_id))

    def require(self, tenant_id: str) -> TenantConfigSnapshot:
        snapshot = self.get(tenant_id)
        if snapshot is None:
            raise KeyError(f"missing tenant config: {tenant_id}")
        return snapshot

    def list_all(self) -> tuple[TenantConfigSnapshot, ...]:
        with self._lock:
            return tuple(sorted(self._snapshots.values(), key=lambda item: item.tenant_id))

    def save(
        self,
        snapshot: TenantConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> TenantConfigSnapshot:
        normalized = snapshot.normalized()
        normalized.validate()
        tenant_id = require_tenant_id(normalized.tenant_id)
        with self._lock:
            previous = self._snapshots.get(tenant_id)
            if previous is not None and expected_revision is not None and int(previous.version.revision if previous.version else 1) != int(expected_revision):
                raise RuntimeError("tenant config optimistic concurrency check failed")
            next_version = ConfigVersioning.create(
                namespace=_TENANT_NAMESPACE,
                entity_id=normalized.entity_id(),
                payload=normalized.payload_for_versioning(),
                previous=None if previous is None else previous.version,
                created_by=actor,
                change_reason=reason,
                labels=normalized.labels,
            )
            if previous is not None and previous.version is not None and next_version.fingerprint == previous.version.fingerprint:
                return previous
            stored = TenantConfigSnapshot(
                tenant_id=tenant_id,
                runtime_overrides=to_jsonable(dict(normalized.runtime_overrides)),
                policy_overrides={str(k): to_jsonable(dict(v)) for k, v in dict(normalized.policy_overrides).items()},
                feature_flags={str(k): bool(v) for k, v in dict(normalized.feature_flags).items()},
                feature_variants={str(k): str(v) for k, v in dict(normalized.feature_variants).items()},
                labels={str(k): str(v) for k, v in dict(normalized.labels).items()},
                updated_at=utc_now(),
                version=next_version,
            )
            stored.validate()
            self._snapshots[tenant_id] = stored
            self._history.setdefault(tenant_id, []).append(stored)
            return stored

    def history(self, tenant_id: str) -> tuple[TenantConfigSnapshot, ...]:
        with self._lock:
            return tuple(self._history.get(require_tenant_id(tenant_id), ()))


class PersistentTenantConfigStore(InMemoryTenantConfigStore):
    def __init__(self, *, path: str | Path | None = None, audit_log_path: str | Path | None = None) -> None:
        super().__init__()
        self._path = Path(path) if path is not None else tenant_config_store_path()
        self._audit_log = PersistentConfigAuditLog(
            Path(audit_log_path) if audit_log_path is not None else tenant_config_audit_log_path()
        )
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def save(
        self,
        snapshot: TenantConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> TenantConfigSnapshot:
        before = self.get(snapshot.tenant_id)
        stored = super().save(snapshot, actor=actor, reason=reason, expected_revision=expected_revision)
        if before is stored:
            return stored
        self._flush()
        self._audit_log.append(
            ConfigAuditEvent(
                namespace=_TENANT_NAMESPACE,
                entity_id=stored.entity_id(),
                tenant_id=stored.tenant_id,
                action="upsert",
                actor=actor,
                version_id=None if stored.version is None else stored.version.version_id,
                payload={
                    "tenant_id": stored.tenant_id,
                    "runtime_override_keys": sorted(stored.runtime_overrides.keys()),
                    "policy_override_keys": sorted(stored.policy_overrides.keys()),
                    "feature_flag_keys": sorted(stored.feature_flags.keys()),
                },
            )
        )
        return stored

    def _load(self) -> None:
        payload = read_json_or_default(self._path, default={"items": []})
        rows = dict(payload).get("items", []) if isinstance(payload, dict) else []
        for row in rows:
            snapshot = TenantConfigSnapshot.from_dict(dict(row))
            tenant_id = require_tenant_id(snapshot.tenant_id)
            self._snapshots[tenant_id] = snapshot
            self._history.setdefault(tenant_id, []).append(snapshot)

    def _flush(self) -> None:
        atomic_write_json(self._path, {"items": [snapshot.to_dict() for snapshot in self.list_all()]})


def tenant_config_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_CONFIG_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "tenant_config_store.json"


def tenant_config_audit_log_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_CONFIG_AUDIT_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "tenant_config_audit.jsonl"


__all__ = [
    "CANON_TENANT_CONFIG_STORE",
    "InMemoryTenantConfigStore",
    "PersistentTenantConfigStore",
    "TenantConfigSnapshot",
    "tenant_config_audit_log_path",
    "tenant_config_store_path",
]
