from __future__ import annotations

import base64
import json
import os
import secrets
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Protocol

from security.key_management_contract import KeyMaterialRecord, KeyPurpose, KeyStatus, utc_now


CANON_KEY_PROVIDER = True


def _key_provider_dir() -> Path:
    data_dir = os.getenv("BUSINESAIOS_DATA_DIR", os.getenv("DATA_DIR", "data")).strip() or "data"
    root = Path(data_dir) / "security"
    root.mkdir(parents=True, exist_ok=True)
    return root


def describe_key_provider_backend() -> str:
    return os.getenv("BUSINESAIOS_KEY_PROVIDER_BACKEND", "file").strip().lower() or "file"


def key_provider_store_path() -> Path:
    return _key_provider_dir() / "key_provider.json"


def key_provider_sqlite_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_KEY_PROVIDER_SQLITE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _key_provider_dir() / "key_provider.sqlite3"


def _serialize_record(record: KeyMaterialRecord) -> dict[str, object]:
    return {
        "key_id": record.key_id,
        "purpose": record.purpose.value,
        "secret_b64": base64.b64encode(bytes(record.secret_bytes)).decode("ascii"),
        "tenant_id": record.tenant_id,
        "connector_id": record.connector_id,
        "status": record.status.value,
        "created_at": record.created_at.isoformat(),
        "activated_at": record.activated_at.isoformat(),
        "expires_at": None if record.expires_at is None else record.expires_at.isoformat(),
        "metadata": dict(record.metadata or {}),
    }


def _deserialize_record(payload: dict[str, object]) -> KeyMaterialRecord:
    expires_raw = payload.get("expires_at")
    return KeyMaterialRecord(
        key_id=str(payload.get("key_id") or "").strip(),
        purpose=KeyPurpose(str(payload.get("purpose") or "")),
        secret_bytes=base64.b64decode(str(payload.get("secret_b64") or "")),
        tenant_id=None if payload.get("tenant_id") in {None, ""} else str(payload.get("tenant_id")),
        connector_id=None if payload.get("connector_id") in {None, ""} else str(payload.get("connector_id")),
        status=KeyStatus(str(payload.get("status") or KeyStatus.ACTIVE.value)),
        created_at=datetime.fromisoformat(str(payload.get("created_at"))),
        activated_at=datetime.fromisoformat(str(payload.get("activated_at"))),
        expires_at=None if expires_raw in {None, ""} else datetime.fromisoformat(str(expires_raw)),
        metadata=dict(payload.get("metadata") or {}),
    )


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".key_provider_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class KeyProvider(Protocol):
    def issue_key(
        self,
        *,
        key_id: str,
        purpose: KeyPurpose,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        expires_in_seconds: int | None = None,
    ) -> KeyMaterialRecord: ...

    def register(self, record: KeyMaterialRecord) -> None: ...

    def get(self, key_id: str) -> KeyMaterialRecord: ...

    def get_active_for(
        self,
        *,
        purpose: KeyPurpose,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        at: datetime | None = None,
    ) -> KeyMaterialRecord: ...


class InMemoryKeyProvider:
    def __init__(self, records: Iterable[KeyMaterialRecord] | None = None) -> None:
        self._records: dict[str, KeyMaterialRecord] = {}
        for record in records or ():
            self.register(record)

    def issue_key(
        self,
        *,
        key_id: str,
        purpose: KeyPurpose,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        expires_in_seconds: int | None = None,
    ) -> KeyMaterialRecord:
        expires_at = None
        if expires_in_seconds is not None:
            ttl = int(expires_in_seconds)
            if ttl <= 0:
                raise ValueError("expires_in_seconds must be > 0")
            expires_at = utc_now() + timedelta(seconds=ttl)
        record = KeyMaterialRecord(
            key_id=str(key_id),
            purpose=purpose,
            secret_bytes=secrets.token_bytes(32),
            tenant_id=tenant_id,
            connector_id=connector_id,
            expires_at=expires_at,
        )
        self.register(record)
        return record

    def register(self, record: KeyMaterialRecord) -> None:
        record.validate()
        self._records[record.key_id] = record

    def get(self, key_id: str) -> KeyMaterialRecord:
        record = self._records.get(str(key_id))
        if record is None:
            raise KeyError(f"unknown key_id: {key_id}")
        return record

    def get_active_for(
        self,
        *,
        purpose: KeyPurpose,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        at: datetime | None = None,
    ) -> KeyMaterialRecord:
        moment = at or utc_now()
        candidates = [
            record
            for record in self._records.values()
            if record.purpose is purpose
            and (tenant_id is None or record.tenant_id == tenant_id)
            and (connector_id is None or record.connector_id == connector_id)
            and record.is_usable(at=moment)
        ]
        if not candidates:
            raise KeyError(f"no active key for purpose={purpose.value}")
        candidates.sort(key=lambda item: (item.activated_at, item.created_at, item.key_id), reverse=True)
        return candidates[0]

    def revoke(self, key_id: str) -> KeyMaterialRecord:
        current = self.get(key_id)
        updated = replace(
            current,
            status=KeyStatus.REVOKED,
            metadata={**dict(current.metadata or {}), "status_changed_at": utc_now().isoformat(), "status_changed_to": KeyStatus.REVOKED.value},
        )
        self._records[key_id] = updated
        return updated

    def compromise(self, key_id: str) -> KeyMaterialRecord:
        current = self.get(key_id)
        updated = replace(
            current,
            status=KeyStatus.COMPROMISED,
            metadata={**dict(current.metadata or {}), "status_changed_at": utc_now().isoformat(), "status_changed_to": KeyStatus.COMPROMISED.value},
        )
        self._records[key_id] = updated
        return updated

    def rotate(self, *, current_key_id: str, new_key_id: str, expires_in_seconds: int | None = None) -> KeyMaterialRecord:
        current = self.get(current_key_id)
        now = utc_now()
        self._records[current_key_id] = replace(
            current,
            status=KeyStatus.DEPRECATED,
            metadata={**dict(current.metadata or {}), "rotated_to_key_id": new_key_id, "rotated_at": now.isoformat()},
        )
        rotated = self.issue_key(
            key_id=new_key_id,
            purpose=current.purpose,
            tenant_id=current.tenant_id,
            connector_id=current.connector_id,
            expires_in_seconds=expires_in_seconds,
        )
        self._records[new_key_id] = replace(rotated, metadata={**dict(rotated.metadata or {}), "rotation_parent_key_id": current.key_id})
        return self._records[new_key_id]

    def list_for_purpose(self, purpose: KeyPurpose) -> tuple[KeyMaterialRecord, ...]:
        records = [record for record in self._records.values() if record.purpose is purpose]
        records.sort(key=lambda item: (item.activated_at, item.created_at, item.key_id), reverse=True)
        return tuple(records)


class FileKeyProvider(InMemoryKeyProvider):
    def __init__(self, path: str | Path | None = None, records: Iterable[KeyMaterialRecord] | None = None) -> None:
        self._path = Path(path) if path is not None else key_provider_store_path()
        super().__init__(records=None)
        self._load()
        for record in records or ():
            self.register(record)

    @property
    def path(self) -> Path:
        return self._path

    def register(self, record: KeyMaterialRecord) -> None:
        super().register(record)
        self._flush()

    def revoke(self, key_id: str) -> KeyMaterialRecord:
        updated = super().revoke(key_id)
        self._flush()
        return updated

    def compromise(self, key_id: str) -> KeyMaterialRecord:
        updated = super().compromise(key_id)
        self._flush()
        return updated

    def rotate(self, *, current_key_id: str, new_key_id: str, expires_in_seconds: int | None = None) -> KeyMaterialRecord:
        updated = super().rotate(current_key_id=current_key_id, new_key_id=new_key_id, expires_in_seconds=expires_in_seconds)
        self._flush()
        return updated

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._records.clear()
        for item in payload.get("records") or []:
            try:
                super().register(_deserialize_record(dict(item)))
            except Exception:
                continue

    def _flush(self) -> None:
        _atomic_write_json(self._path, {"records": [_serialize_record(record) for record in self._records.values()]})
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass


def build_default_key_provider() -> KeyProvider:
    mode = describe_key_provider_backend()
    if mode in {"memory", "inmemory"}:
        return InMemoryKeyProvider()
    if mode == "sqlite":
        from security.key_provider_sqlite import SqliteKeyProvider, SqliteKeyProviderBackend

        return SqliteKeyProvider(SqliteKeyProviderBackend(key_provider_sqlite_path()))
    return FileKeyProvider()


__all__ = [
    "CANON_KEY_PROVIDER",
    "FileKeyProvider",
    "InMemoryKeyProvider",
    "KeyProvider",
    "build_default_key_provider",
    "describe_key_provider_backend",
    "key_provider_sqlite_path",
    "key_provider_store_path",
]
