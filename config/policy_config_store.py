from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.config_versioning import ConfigVersion, utc_now
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
CANON_POLICY_CONFIG_STORE = True

_POLICY_NAMESPACE = "policy_config"


def _normalized_optional_tenant_id(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("tenant_id must be a string or None")
    normalized = normalize_tenant_id(value)
    return normalized or None


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
class PolicyConfigSnapshot:
    policy_name: str
    tenant_id: str | None = None
    scope: str = "global"
    config: Mapping[str, Any] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utc_now)
    version: ConfigVersion | None = None

    def validate(self) -> None:
        require_text("policy_name", self.policy_name)
        require_text("scope", self.scope)
        _normalized_optional_tenant_id(self.tenant_id)
        require_timezone_aware("updated_at", self.updated_at)
        canonical_config_snapshot(self.config)
        canonical_labels(self.labels)
        if self.version is not None:
            if not isinstance(self.version, ConfigVersion):
                raise ValueError("version must be a ConfigVersion")
            self.version.validate()

    def normalized(self) -> PolicyConfigSnapshot:
        return PolicyConfigSnapshot(
            policy_name=require_text("policy_name", self.policy_name),
            tenant_id=_normalized_optional_tenant_id(self.tenant_id),
            scope=require_text("scope", self.scope),
            config=canonical_config_snapshot(self.config),
            labels=canonical_labels(self.labels),
            updated_at=self.updated_at,
            version=self.version,
        )

    def with_version(self, *, version: ConfigVersion, updated_at: datetime) -> PolicyConfigSnapshot:
        return replace(self.normalized(), version=version, updated_at=updated_at)

    def entity_id(self) -> str:
        normalized = self.normalized()
        return f"{normalized.tenant_id or 'global'}:{normalized.scope}:{normalized.policy_name}"

    def payload_for_versioning(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            "policy_name": normalized.policy_name,
            "tenant_id": normalized.tenant_id,
            "scope": normalized.scope,
            "config": canonical_config_snapshot(normalized.config),
            "labels": canonical_labels(normalized.labels),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> PolicyConfigSnapshot:
        if not isinstance(payload, Mapping):
            raise ValueError("policy config payload must be a mapping")
        item = dict(payload)
        raw_version = item.get("version")
        if raw_version is not None and not isinstance(raw_version, Mapping):
            raise ValueError("version must be a mapping or None")
        version = None if raw_version is None else ConfigVersion.from_dict(raw_version)
        raw_config = item.get("config", {})
        raw_labels = item.get("labels", {})
        snapshot = cls(
            policy_name=item.get("policy_name"),
            tenant_id=item.get("tenant_id"),
            scope=item.get("scope", "global"),
            config=raw_config,
            labels=raw_labels,
            updated_at=_parse_datetime(item.get("updated_at")),
            version=version,
        ).normalized()
        snapshot.validate()
        return snapshot

    def to_dict(self) -> dict[str, object]:
        normalized = self.normalized()
        normalized.validate()
        return {
            "policy_name": normalized.policy_name,
            "tenant_id": normalized.tenant_id,
            "scope": normalized.scope,
            "config": canonical_config_snapshot(normalized.config),
            "labels": canonical_labels(normalized.labels),
            "updated_at": normalized.updated_at.isoformat(),
            "version": None if normalized.version is None else normalized.version.to_dict(),
        }


class _PolicyConfigStoreApi:
    def get(self, *, policy_name: str, tenant_id: str | None = None, scope: str = "global") -> PolicyConfigSnapshot | None:
        return self._get_by_key(self._key(policy_name=policy_name, tenant_id=tenant_id, scope=scope))

    def require(self, *, policy_name: str, tenant_id: str | None = None, scope: str = "global") -> PolicyConfigSnapshot:
        return self._require_by_key(
            self._key(policy_name=policy_name, tenant_id=tenant_id, scope=scope),
            message=f"missing policy config: {policy_name}",
        )

    def list_all(self) -> tuple[PolicyConfigSnapshot, ...]:
        return self._list_all()

    def history(self, *, policy_name: str, tenant_id: str | None = None, scope: str = "global") -> tuple[PolicyConfigSnapshot, ...]:
        return self._history_by_key(self._key(policy_name=policy_name, tenant_id=tenant_id, scope=scope))

    @staticmethod
    def _key(*, policy_name: str, tenant_id: str | None, scope: str) -> str:
        return f"{_normalized_optional_tenant_id(tenant_id) or 'global'}::{require_text('scope', scope)}::{require_text('policy_name', policy_name)}"

    @staticmethod
    def _snapshot_key(snapshot: PolicyConfigSnapshot) -> str:
        return _PolicyConfigStoreApi._key(
            policy_name=snapshot.policy_name,
            tenant_id=snapshot.tenant_id,
            scope=snapshot.scope,
        )


class InMemoryPolicyConfigStore(_PolicyConfigStoreApi, InMemoryVersionedConfigStore[PolicyConfigSnapshot]):
    def __init__(self) -> None:
        InMemoryVersionedConfigStore.__init__(
            self,
            namespace=_POLICY_NAMESPACE,
            snapshot_type=PolicyConfigSnapshot,
            key_for_snapshot=self._snapshot_key,
        )

    def save(
        self,
        snapshot: PolicyConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> PolicyConfigSnapshot:
        return self._save_snapshot(
            snapshot,
            actor=actor,
            reason=reason,
            expected_revision=expected_revision,
        )


class PersistentPolicyConfigStore(_PolicyConfigStoreApi, PersistentVersionedConfigStore[PolicyConfigSnapshot]):
    def __init__(self, *, path: str | Path | None = None, audit_log_path: str | Path | None = None) -> None:
        PersistentVersionedConfigStore.__init__(
            self,
            namespace=_POLICY_NAMESPACE,
            snapshot_type=PolicyConfigSnapshot,
            key_for_snapshot=self._snapshot_key,
            snapshot_from_dict=PolicyConfigSnapshot.from_dict,
            audit_payload=lambda snapshot: {
                "policy_name": snapshot.policy_name,
                "scope": snapshot.scope,
                "labels": dict(snapshot.labels),
            },
            path=policy_config_store_path() if path is None else path,
            audit_log_path=policy_config_audit_log_path() if audit_log_path is None else audit_log_path,
        )

    def save(
        self,
        snapshot: PolicyConfigSnapshot,
        *,
        actor: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
    ) -> PolicyConfigSnapshot:
        return self._save_persistent_snapshot(
            snapshot,
            actor=actor,
            reason=reason,
            expected_revision=expected_revision,
        )


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
