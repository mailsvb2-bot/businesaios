from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Generic, Protocol, TypeVar, cast

from config.config_audit import ConfigAuditEvent, PersistentConfigAuditLog
from config.config_versioning import ConfigVersion, ConfigVersioning, utc_now
from governance.persistence_codec import atomic_write_json, read_json_or_default, to_jsonable

CANON_VERSIONED_CONFIG_STORE = True


class VersionedConfigSnapshot(Protocol):
    tenant_id: str | None
    version: ConfigVersion | None

    def validate(self) -> None: ...

    def normalized(self): ...

    def entity_id(self) -> str: ...

    def payload_for_versioning(self) -> Mapping[str, Any]: ...

    def with_version(self, *, version: ConfigVersion, updated_at): ...

    def to_dict(self) -> dict[str, object]: ...


SnapshotT = TypeVar("SnapshotT", bound=VersionedConfigSnapshot)


def canonical_config_snapshot(value: object) -> Any:
    _reject_unstable_collections(value)
    normalized = to_jsonable(value)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return json.loads(encoded)


def canonical_labels(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("labels must be a mapping")
    labels: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("label keys must be non-empty strings")
        if not isinstance(item, str):
            raise ValueError("label values must be strings")
        normalized_key = key.strip()
        if normalized_key in labels:
            raise ValueError("duplicate normalized label key")
        labels[normalized_key] = item
    return labels


def require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def require_optional_revision(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or type(value) is not int:
        raise ValueError("expected_revision must be an integer")
    if value < 1:
        raise ValueError("expected_revision must be >= 1")
    return value


def require_reason(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("reason must be a string")
    return value.strip()


def require_timezone_aware(name: str, value: object) -> None:
    if not hasattr(value, "utcoffset") or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _reject_unstable_collections(value: object) -> None:
    if isinstance(value, (set, frozenset, bytes, bytearray, memoryview)):
        raise ValueError("config values must be deterministic JSON-compatible data")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("config numeric values must be finite")
    if isinstance(value, Mapping):
        seen: set[str] = set()
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("config mapping keys must be strings")
            if key in seen:
                raise ValueError("duplicate config mapping key")
            seen.add(key)
            _reject_unstable_collections(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_unstable_collections(item)


@dataclass(frozen=True)
class _PreparedSave(Generic[SnapshotT]):
    key: str
    previous: SnapshotT | None
    stored: SnapshotT
    unchanged: bool


class InMemoryVersionedConfigStore(Generic[SnapshotT]):
    """Single passive owner for immutable versioned configuration state.

    Domain adapters provide key construction and snapshot codecs. This store owns
    versioning, optimistic concurrency, defensive copies, and history only. It
    never evaluates configuration or makes product/business decisions.
    """

    def __init__(
        self,
        *,
        namespace: str,
        snapshot_type: type[SnapshotT],
        key_for_snapshot: Callable[[SnapshotT], str],
    ) -> None:
        self._namespace = require_text("namespace", namespace)
        self._snapshot_type = snapshot_type
        self._key_for_snapshot = key_for_snapshot
        self._snapshots: dict[str, SnapshotT] = {}
        self._history: dict[str, list[SnapshotT]] = {}
        self._lock = RLock()

    def _get_by_key(self, key: str) -> SnapshotT | None:
        normalized_key = require_text("config key", key)
        with self._lock:
            value = self._snapshots.get(normalized_key)
            return None if value is None else deepcopy(value)

    def _require_by_key(self, key: str, *, message: str) -> SnapshotT:
        value = self._get_by_key(key)
        if value is None:
            raise KeyError(message)
        return value

    def _list_all(self) -> tuple[SnapshotT, ...]:
        with self._lock:
            values = sorted(self._snapshots.values(), key=lambda item: item.entity_id())
            return tuple(deepcopy(item) for item in values)

    def _history_by_key(self, key: str) -> tuple[SnapshotT, ...]:
        normalized_key = require_text("config key", key)
        with self._lock:
            return tuple(deepcopy(item) for item in self._history.get(normalized_key, ()))

    def _save_snapshot(
        self,
        snapshot: SnapshotT,
        *,
        actor: str,
        reason: str,
        expected_revision: int | None,
    ) -> SnapshotT:
        normalized_actor = require_text("actor", actor)
        normalized_reason = require_reason(reason)
        normalized_revision = require_optional_revision(expected_revision)
        with self._lock:
            prepared = self._prepare_save_unlocked(
                snapshot,
                actor=normalized_actor,
                reason=normalized_reason,
                expected_revision=normalized_revision,
            )
            if prepared.unchanged:
                return deepcopy(prepared.stored)
            self._commit_unlocked(prepared)
            return deepcopy(prepared.stored)

    def _prepare_save_unlocked(
        self,
        snapshot: SnapshotT,
        *,
        actor: str,
        reason: str,
        expected_revision: int | None,
    ) -> _PreparedSave[SnapshotT]:
        if not isinstance(snapshot, self._snapshot_type):
            raise ValueError(f"snapshot must be a {self._snapshot_type.__name__}")
        normalized = cast(SnapshotT, snapshot.normalized())
        normalized.validate()
        key = require_text("config key", self._key_for_snapshot(normalized))
        previous = self._snapshots.get(key)
        if expected_revision is not None:
            if previous is None:
                raise RuntimeError("config optimistic concurrency check failed: snapshot does not exist")
            current_revision = previous.version.revision if previous.version is not None else 1
            if current_revision != expected_revision:
                raise RuntimeError("config optimistic concurrency check failed")
        next_version = ConfigVersioning.create(
            namespace=self._namespace,
            entity_id=normalized.entity_id(),
            payload=normalized.payload_for_versioning(),
            previous=None if previous is None else previous.version,
            created_by=actor,
            change_reason=reason,
            labels=canonical_labels(getattr(normalized, "labels", {})),
        )
        if previous is not None and previous.version is not None and next_version.fingerprint == previous.version.fingerprint:
            return _PreparedSave(key=key, previous=previous, stored=previous, unchanged=True)
        stored = cast(SnapshotT, normalized.with_version(version=next_version, updated_at=utc_now()))
        stored.validate()
        return _PreparedSave(key=key, previous=previous, stored=stored, unchanged=False)

    def _commit_unlocked(self, prepared: _PreparedSave[SnapshotT]) -> None:
        internal = deepcopy(prepared.stored)
        self._snapshots[prepared.key] = internal
        self._history.setdefault(prepared.key, []).append(deepcopy(internal))


class PersistentVersionedConfigStore(InMemoryVersionedConfigStore[SnapshotT]):
    def __init__(
        self,
        *,
        namespace: str,
        snapshot_type: type[SnapshotT],
        key_for_snapshot: Callable[[SnapshotT], str],
        snapshot_from_dict: Callable[[Mapping[str, object]], SnapshotT],
        audit_payload: Callable[[SnapshotT], Mapping[str, object]],
        path: str | Path,
        audit_log_path: str | Path,
    ) -> None:
        super().__init__(
            namespace=namespace,
            snapshot_type=snapshot_type,
            key_for_snapshot=key_for_snapshot,
        )
        self._path = _require_path("path", path)
        self._audit_log = PersistentConfigAuditLog(_require_path("audit_log_path", audit_log_path))
        self._snapshot_from_dict = snapshot_from_dict
        self._audit_payload = audit_payload
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _save_persistent_snapshot(
        self,
        snapshot: SnapshotT,
        *,
        actor: str,
        reason: str,
        expected_revision: int | None,
    ) -> SnapshotT:
        normalized_actor = require_text("actor", actor)
        normalized_reason = require_reason(reason)
        normalized_revision = require_optional_revision(expected_revision)
        with self._lock:
            prepared = self._prepare_save_unlocked(
                snapshot,
                actor=normalized_actor,
                reason=normalized_reason,
                expected_revision=normalized_revision,
            )
            if prepared.unchanged:
                return deepcopy(prepared.stored)
            previous_payload = self._serialized_payload_unlocked()
            candidate_snapshots = dict(self._snapshots)
            candidate_snapshots[prepared.key] = deepcopy(prepared.stored)
            candidate_payload = self._serialized_payload(candidate_snapshots)
            atomic_write_json(self._path, candidate_payload)
            try:
                self._audit_log.append(
                    ConfigAuditEvent(
                        namespace=self._namespace,
                        entity_id=prepared.stored.entity_id(),
                        tenant_id=prepared.stored.tenant_id,
                        action="upsert",
                        actor=normalized_actor,
                        version_id=None if prepared.stored.version is None else prepared.stored.version.version_id,
                        payload=canonical_config_snapshot(dict(self._audit_payload(prepared.stored))),
                    )
                )
            except Exception as audit_error:
                try:
                    atomic_write_json(self._path, previous_payload)
                except Exception as rollback_error:
                    raise RuntimeError("config audit failed and persistence rollback failed") from rollback_error
                raise audit_error
            self._commit_unlocked(prepared)
            return deepcopy(prepared.stored)

    def _load(self) -> None:
        payload = read_json_or_default(self._path, default={"items": []})
        if not isinstance(payload, Mapping):
            raise ValueError("config store payload must be a mapping")
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("config store items must be a list")
        loaded: dict[str, SnapshotT] = {}
        for row in raw_items:
            if not isinstance(row, Mapping):
                raise ValueError("config store item must be a mapping")
            snapshot = self._snapshot_from_dict(row)
            if not isinstance(snapshot, self._snapshot_type):
                raise ValueError(f"snapshot codec must return {self._snapshot_type.__name__}")
            normalized = cast(SnapshotT, snapshot.normalized())
            normalized.validate()
            key = require_text("config key", self._key_for_snapshot(normalized))
            if key in loaded:
                raise ValueError("duplicate config snapshot key")
            loaded[key] = deepcopy(normalized)
        with self._lock:
            self._snapshots = loaded
            self._history = {key: [deepcopy(value)] for key, value in loaded.items()}

    def _serialized_payload_unlocked(self) -> dict[str, object]:
        return self._serialized_payload(self._snapshots)

    @staticmethod
    def _serialized_payload(snapshots: Mapping[str, SnapshotT]) -> dict[str, object]:
        values = sorted(snapshots.values(), key=lambda item: item.entity_id())
        return {"items": [item.to_dict() for item in values]}


def _require_path(name: str, value: str | Path) -> Path:
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str) and value.strip():
        path = Path(value.strip())
    else:
        raise ValueError(f"{name} is required")
    if str(path).strip() in {"", "."}:
        raise ValueError(f"{name} must identify a file")
    return path


__all__ = [
    "CANON_VERSIONED_CONFIG_STORE",
    "InMemoryVersionedConfigStore",
    "PersistentVersionedConfigStore",
    "VersionedConfigSnapshot",
    "canonical_config_snapshot",
    "canonical_labels",
    "require_optional_revision",
    "require_reason",
    "require_text",
    "require_timezone_aware",
]
