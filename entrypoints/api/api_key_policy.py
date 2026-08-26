from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from entrypoints.api.auth_contract import AuthMechanism, AuthPrincipal, AuthVerdict, RequestAuthentication
from governance.persistence_codec import (
    atomic_write_json,
    exclusive_file_lock,
    from_dataclass,
    read_json_or_default,
    to_jsonable,
)
from governance.rbac_contract import RoleId

CANON_API_KEY_POLICY = True
CANON_API_FINAL_OWNER = True
OWNER_SESSION_RESUME_SCOPE = 'owner_session_resume'


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _derive_secret_hash(*, secret: str, pepper: str = '') -> str:
    if not str(secret or '').strip():
        raise ValueError('secret is required')
    return hashlib.sha256(f'{pepper}|{secret}'.encode('utf-8')).hexdigest()


def _deny(reason: str, *, mechanism: AuthMechanism | None = AuthMechanism.API_KEY) -> AuthVerdict:
    verdict = AuthVerdict(allowed=False, reason=reason, mechanism=mechanism, challenge='ApiKey')
    verdict.validate(); return verdict


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    secret_hash: str
    tenant_id: str
    subject: str
    actor_id: str | None = None
    roles: tuple[RoleId, ...] = ()
    scopes: tuple[str, ...] = ()
    display_name: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.key_id or '').strip():
            raise ValueError('key_id is required')
        if not str(self.secret_hash or '').strip():
            raise ValueError('secret_hash is required')
        if not str(self.tenant_id or '').strip():
            raise ValueError('tenant_id is required')
        if not str(self.subject or '').strip():
            raise ValueError('subject is required')
        if self.created_at.tzinfo is None:
            raise ValueError('created_at must be timezone-aware')
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError('expires_at must be timezone-aware')
        if self.revoked_at is not None and self.revoked_at.tzinfo is None:
            raise ValueError('revoked_at must be timezone-aware')

    def is_active(self, *, now: datetime | None = None) -> bool:
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        return not ((self.revoked_at is not None and self.revoked_at <= moment) or (self.expires_at is not None and self.expires_at <= moment))


class InMemoryApiKeyStore:
    def __init__(self, records: tuple[ApiKeyRecord, ...] = (), *, pepper: str = '') -> None:
        self._records: dict[str, ApiKeyRecord] = {}
        self._pepper = str(pepper)
        for record in records:
            self.register(record)

    @property
    def pepper(self) -> str:
        return self._pepper

    def register(self, record: ApiKeyRecord) -> ApiKeyRecord:
        record.validate()
        self._records[record.key_id] = record
        return record

    def issue(self, *, tenant_id: str, subject: str, actor_id: str | None = None, roles: tuple[RoleId, ...] = (), scopes: tuple[str, ...] = (), display_name: str | None = None, ttl_seconds: int | None = None, metadata: Mapping[str, object] | None = None) -> tuple[ApiKeyRecord, str]:
        raw_secret = secrets.token_urlsafe(32)
        key_id = f'ak_{secrets.token_hex(8)}'
        expires_at = None if ttl_seconds is None else utc_now() + timedelta(seconds=int(ttl_seconds))
        record = ApiKeyRecord(key_id=key_id, secret_hash=_derive_secret_hash(secret=raw_secret, pepper=self._pepper), tenant_id=str(tenant_id), subject=str(subject), actor_id=actor_id, roles=tuple(roles), scopes=tuple(str(item) for item in scopes), display_name=display_name, expires_at=expires_at, metadata=dict(metadata or {}))
        self.register(record)
        return record, f'{key_id}.{raw_secret}'

    def get(self, key_id: str) -> ApiKeyRecord | None:
        return self._records.get(str(key_id))

    def list_records(self) -> tuple[ApiKeyRecord, ...]:
        return tuple(self._records.values())

    def verify_secret(self, *, key_id: str, raw_secret: str) -> bool:
        record = self.get(key_id)
        if record is None:
            return False
        presented_hash = _derive_secret_hash(secret=raw_secret, pepper=self._pepper)
        return hmac.compare_digest(record.secret_hash, presented_hash)

    def revoke(self, key_id: str, *, at: datetime | None = None) -> ApiKeyRecord:
        record = self._records[str(key_id)]
        updated = replace(record, revoked_at=at or utc_now())
        self._records[str(key_id)] = updated
        return updated

    def rotate_owner_session(self, *, tenant_id: str, business_id: str, subject: str, display_name: str | None = None, ttl_seconds: int = 3600) -> tuple[ApiKeyRecord, str]:
        now = utc_now()
        for record in self.list_records():
            metadata = dict(record.metadata or {})
            if record.is_active(now=now) and record.tenant_id == str(tenant_id) and record.subject == str(subject) and str(metadata.get('session_kind') or '') == 'owner_onboarding' and str(metadata.get('business_id') or '') == str(business_id):
                self._records[record.key_id] = replace(record, revoked_at=now)
        raw_secret, key_id = secrets.token_urlsafe(32), f'ak_{secrets.token_hex(8)}'
        record = ApiKeyRecord(key_id=key_id, secret_hash=_derive_secret_hash(secret=raw_secret, pepper=self._pepper), tenant_id=str(tenant_id), subject=str(subject), actor_id=subject, roles=(RoleId.OWNER,), scopes=('provider_control_plane',), display_name=display_name, expires_at=now + timedelta(seconds=int(ttl_seconds)), metadata={'principal_kind': 'user', 'session_kind': 'owner_onboarding', 'business_id': business_id})
        InMemoryApiKeyStore.register(self, record)
        return record, f'{key_id}.{raw_secret}'


def api_key_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_API_KEY_STORE_PATH", "").strip()
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(explicit) if explicit else Path(data_dir) / "api" / "api_keys.json"


class PersistentApiKeyStore(InMemoryApiKeyStore):
    def __init__(self, records: tuple[ApiKeyRecord, ...] = (), *, pepper: str = '', path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else api_key_store_path()
        super().__init__((), pepper=pepper)
        self._load()
        for record in records:
            self.register(record)

    @property
    def path(self) -> Path:
        return self._path

    def register(self, record: ApiKeyRecord) -> ApiKeyRecord:
        with exclusive_file_lock(self._path):
            self._load()
            saved = super().register(record)
            self._flush()
            return saved

    def revoke(self, key_id: str, *, at: datetime | None = None) -> ApiKeyRecord:
        with exclusive_file_lock(self._path):
            self._load()
            updated = super().revoke(key_id, at=at)
            self._flush()
            return updated

    def rotate_owner_session(self, *, tenant_id: str, business_id: str, subject: str, display_name: str | None = None, ttl_seconds: int = 3600) -> tuple[ApiKeyRecord, str]:
        with exclusive_file_lock(self._path):
            self._load()
            result = super().rotate_owner_session(tenant_id=tenant_id, business_id=business_id, subject=subject, display_name=display_name, ttl_seconds=ttl_seconds)
            self._flush()
            return result

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"records": []})
        items = raw.get("records", []) if isinstance(raw, dict) else []
        self._records = {}
        for item in items:
            record = from_dataclass(ApiKeyRecord, dict(item))
            self._records[record.key_id] = record

    def _flush(self) -> None:
        atomic_write_json(self._path, {"records": [to_jsonable(item) for item in self._records.values()]})


def build_default_api_key_store(*, pepper: str = '') -> InMemoryApiKeyStore:
    mode = os.getenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "file").strip().lower()
    return InMemoryApiKeyStore(pepper=pepper) if mode == 'memory' else PersistentApiKeyStore(pepper=pepper)


class ApiKeyPolicy:
    def __init__(self, *, store: InMemoryApiKeyStore) -> None:
        self._store = store

    def issue_owner_session(self, *, tenant_id: str, business_id: str, subject: str, display_name: str | None = None, ttl_seconds: int = 3600) -> tuple[ApiKeyRecord, str]:
        return self._store.issue(tenant_id=tenant_id, subject=subject, actor_id=subject, roles=(RoleId.OWNER,), scopes=('provider_control_plane',), display_name=display_name, ttl_seconds=ttl_seconds, metadata={'principal_kind': 'user', 'session_kind': 'owner_onboarding', 'business_id': business_id})

    def issue_owner_resume_session(self, *, tenant_id: str, business_id: str, intake_id: str, subject: str, display_name: str | None = None, ttl_seconds: int = 86400) -> tuple[ApiKeyRecord, str]:
        metadata = {'principal_kind': 'user', 'session_kind': 'owner_onboarding_resume', 'business_id': business_id, 'intake_id': intake_id}
        return self._store.issue(tenant_id=tenant_id, subject=subject, actor_id=subject, roles=(), scopes=(OWNER_SESSION_RESUME_SCOPE,), display_name=display_name, ttl_seconds=ttl_seconds, metadata=metadata)

    def resume_owner_session(self, *, resume_key: str, intake_id: str, tenant_id: str, business_id: str, ttl_seconds: int = 3600) -> tuple[ApiKeyRecord, str] | None:
        verdict = self.authenticate(RequestAuthentication(tenant_id=tenant_id, api_key=resume_key))
        principal = verdict.principal
        if not verdict.allowed or principal is None:
            return None
        metadata = dict(principal.metadata or {})
        if tuple(principal.roles) or tuple(principal.scopes) != (OWNER_SESSION_RESUME_SCOPE,) or str(metadata.get('session_kind') or '') != 'owner_onboarding_resume':
            return None
        if str(metadata.get('business_id') or '') != str(business_id) or str(metadata.get('intake_id') or '') != str(intake_id):
            return None
        return self._store.rotate_owner_session(tenant_id=tenant_id, business_id=business_id, subject=principal.subject, display_name=str(metadata.get('display_name') or '') or None, ttl_seconds=ttl_seconds)

    def authenticate(self, request: RequestAuthentication) -> AuthVerdict:
        request.validate()
        token = str(request.api_key or '').strip()
        if not token:
            return _deny('missing_api_key', mechanism=None)
        if '.' not in token:
            return _deny('malformed_api_key')
        key_id, raw_secret = token.split('.', 1)
        record = self._store.get(key_id)
        if record is None:
            return _deny('unknown_api_key')
        if not record.is_active():
            return _deny('inactive_api_key')
        if request.tenant_id and str(request.tenant_id) != record.tenant_id:
            return _deny('tenant_mismatch')
        if not self._store.verify_secret(key_id=key_id, raw_secret=raw_secret):
            return _deny('bad_api_key_secret')
        principal = AuthPrincipal(subject=record.subject, tenant_id=record.tenant_id, actor_id=record.actor_id or record.subject, roles=tuple(record.roles), scopes=tuple(record.scopes), metadata={'auth_type': 'api_key', 'principal_kind': 'service', 'key_id': record.key_id, 'display_name': record.display_name, 'created_at': record.created_at.isoformat(), 'issued_at': record.created_at.isoformat(), 'expires_at': record.expires_at.isoformat() if record.expires_at is not None else None, 'session_created_at': record.created_at.isoformat(), **dict(record.metadata)})
        verdict = AuthVerdict(allowed=True, reason='authenticated', mechanism=AuthMechanism.API_KEY, principal=principal, labels={'key_id': record.key_id})
        verdict.validate()
        return verdict


__all__ = ['ApiKeyPolicy', 'ApiKeyRecord', 'CANON_API_KEY_POLICY', 'InMemoryApiKeyStore', 'OWNER_SESSION_RESUME_SCOPE', 'PersistentApiKeyStore', 'build_default_api_key_store', 'api_key_store_path']
