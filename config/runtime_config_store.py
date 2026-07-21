from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.config_versioning import ConfigVersion, utc_now
from config.environment_matrix import normalize_environment_name
from config.versioned_config_store import (
    InMemoryVersionedConfigStore,
    PersistentVersionedConfigStore,
    canonical_config_snapshot,
    canonical_labels,
    require_text,
    require_timezone_aware,
)
from core.tenancy.normalization import normalize_tenant_id

CANON_COMPAT_SHIM = True
CANON_RUNTIME_CONFIG_STORE = True

_RUNTIME_NAMESPACE = "runtime_config"


def _normalized_optional_tenant_id(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("tenant_id must be a string or None")
    normalized = normalize_tenant_id(value)
    return normalized or None


def _normalized_environment(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("environment must be a string")
    return require_text("environment", normalize_environment_name(value))


def _parse_datetime(value: object) -> datetime:
    if value is None or value == "":
        return utc_now()
    if not isinstance(value, str):
        raise ValueError("updated_at must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


@dataclass(frozen=True)
class RuntimeConfigSnapshot:
    profile_name: str
    environment: str
    tenant_id: str | None = None
    runtime_settings: Mapping[str, Any] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utc_now)
    version: ConfigVersion | None = None

    def validate(self) -> None:
        require_text("profile_name", self.profile_name)
        _normalized_environment(self.environment)
        _normalized_optional_tenant_id(self.tenant_id)
        require_timezone_aware("updated_at", self.updated_at)
        canonical_config_snapshot(self.runtime_settings)
        canonical_labels(self.labels)
        if self.version is not None:
            if not isinstance(self.version, ConfigVersion):
                raise ValueError("version must be a ConfigVersion")
            self.version.validate()

    def normalized(self) -> RuntimeConfigSnapshot:
        return RuntimeConfigSnapshot(
            profile_name=require_text("profile_name", self.profile_name),
            environment=_normalized_environment(self.environment),
            tenant_id=_normalized_optional_tenant_id(self.tenant_id),
            runtime_settings=canonical_config_snapshot(self.runtime_settings),
            labels=canonical_labels(self.labels),
            updated_at=self.updated_at,
            version=self.version,
        )

    def with_version(self, *, version: ConfigVersion, updated_at: datetime) -> RuntimeConfigSnapshot:
        return replace(self.normalized(), version=version, updated_at=updated_at)

    def entity_id(self) -> str:
        normalized = self.normalized()
        return f"{normalized.tenant_id or 'global'}:{normalized.environment}:{normalized.profile_name}"

    def payload_for_versioning(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            "profile_name": normalized.profile_name,
            "environment": normalized.environment,
            "tenant_id": normalized.tenant_id,
            "runtime_settings": canonical_config_snapshot(normalized.runtime_settings),
            "labels": canonical_labels(normalized.labels),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RuntimeConfigSnapshot:
        if not isinstance(payload, Mapping):
            raise ValueError("runtime config payload must be a mapping")
        item = dict(payload)
        raw_version = item.get("version")
        if raw_version is not None and not isinstance(raw_version, Mapping):
            raise ValueError("version must be a mapping or None")
        version = None if raw_version is None else ConfigVersion.from_dict(raw_version)
        snapshot = cls(
            profile_name=item.get("profile_name"),
            environment=item.get("environment"),
            tenant_id=item.get("tenant_id"),
            runtime_settings=item.get("runtime_settings", {}),
            labels=item.get("labels", {}),
            updated_at=_parse_datetime(item.get("updated_at")),
            version=version,
        ).normalized()
        snapshot.validate()
        return snapshot

    def to_dict(self) -> dict[str, object]:
        normalized = self.normalized()
        normalized.validate()
        return {
            "profile_name": normalized.profile_name,
            "environment": normalized.environment,
            "tenant_id": normalized.tenant_id,
            "runtime_settings": canonical_config_snapshot(normalized.runtime_settings),
            "labels": canonical_labels(normalized.labels),
            "updated_at": normalized.updated_at.isoformat(),
            "version": None if normalized.version is None else normalized.version.to_dict(),
        }


class _RuntimeConfigStoreApi:
    def get(self, *, profile_name: str, environment: str, tenant_id: str | None = None) -> RuntimeConfigSnapshot | None:
        return self._get_by_key(
            self._key(profile_name=profile_name, environment=environment, tenant_id=tenant_id)
        )

    def require(self, *, profile_name: str, environment: str, tenant_id: str | None = None) -> RuntimeConfigSnapshot:
        return self._require_by_key(
            self._key(profile_name=profile_name, environment=environment, tenant_id=tenant_id),
            message=f"missing runtime config: {profile_name}",
        )

    def list_all(self) -> tuple[RuntimeConfigSnapshot, ...]:
        return self._list_all()

    def history(self, *, profile_name: str, environment: str, tenant_id: str | None = None) -> tuple[RuntimeConfigSnapshot, ...]:
        return self._history_by_key(
            self._key(profile_name=profile_name, environment=environment, tenant_id=tenant_id)
        )

    @staticmethod
    def _key(*, profile_name: str, environment: str, tenant_id: str | None) -> str:
        return f"{_normalized_optional_tenant_id(tenant_id) or 'global'}::{_normalized_environment(environment)}::{require_text('profile_name', profile_name)}"

    @staticmethod
    def _snapshot_key(snapshot: RuntimeConfigSnapshot) -> str:
        return _RuntimeConfigStoreApi._key(
            profile_name=snapshot.profile_name,
            environment=snapshot.environment,
            tenant_id=snapshot.tenant_id,
        )


class InMemoryRuntimeConfigStore(_RuntimeConfigStoreApi, InMemoryVersionedConfigStore[RuntimeConfigSnapshot]):
    def __init__(self) -> None:
        InMemoryVersionedConfigStore.__init__(
            self,
            namespace=_RUNTIME_NAMESPACE,
            snapshot_type=RuntimeConfigSnapshot,
            key_for_snapshot=self._snapshot_key,
        )

    def save(
        self,
        snapshot: RuntimeConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> RuntimeConfigSnapshot:
        return self._save_snapshot(
            snapshot,
            actor=actor,
            reason=reason,
            expected_revision=expected_revision,
        )


class PersistentRuntimeConfigStore(_RuntimeConfigStoreApi, PersistentVersionedConfigStore[RuntimeConfigSnapshot]):
    def __init__(self, *, path: str | Path | None = None, audit_log_path: str | Path | None = None) -> None:
        PersistentVersionedConfigStore.__init__(
            self,
            namespace=_RUNTIME_NAMESPACE,
            snapshot_type=RuntimeConfigSnapshot,
            key_for_snapshot=self._snapshot_key,
            snapshot_from_dict=RuntimeConfigSnapshot.from_dict,
            audit_payload=lambda snapshot: {
                "profile_name": snapshot.profile_name,
                "environment": snapshot.environment,
                "labels": dict(snapshot.labels),
            },
            path=runtime_config_store_path() if path is None else path,
            audit_log_path=runtime_config_audit_log_path() if audit_log_path is None else audit_log_path,
        )

    def save(
        self,
        snapshot: RuntimeConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> RuntimeConfigSnapshot:
        return self._save_persistent_snapshot(
            snapshot,
            actor=actor,
            reason=reason,
            expected_revision=expected_revision,
        )


def runtime_config_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_RUNTIME_CONFIG_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "runtime_config_store.json"


def runtime_config_audit_log_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_RUNTIME_CONFIG_AUDIT_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "runtime_config_audit.jsonl"


__all__ = [
    "CANON_RUNTIME_CONFIG_STORE",
    "InMemoryRuntimeConfigStore",
    "PersistentRuntimeConfigStore",
    "RuntimeConfigSnapshot",
    "runtime_config_audit_log_path",
    "runtime_config_store_path",
]
