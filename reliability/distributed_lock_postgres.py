from __future__ import annotations

from datetime import datetime, timezone
import threading

from reliability.distributed_lock_contracts import LockLease
from reliability.distributed_lock_backend import DistributedLockBackend, LockBackendRecord, build_expires_at, ensure_aware, normalize_lock_inputs, normalize_resource, safe_sql_identifier
from storage.postgres_session import PostgresSession, PostgresSessionFactory

CANON_DISTRIBUTED_LOCK_POSTGRES = True

class PostgresDistributedLockBackend(DistributedLockBackend):
    def __init__(self, *, dsn: str, application_name: str = 'businesaios-reliability-lock', statement_timeout_ms: int = 30000, lock_timeout_ms: int = 5000, table_prefix: str = 'reliability') -> None:
        prefix = safe_sql_identifier(str(table_prefix or 'reliability').strip())
        self._sessions = PostgresSessionFactory(dsn=str(dsn), application_name=str(application_name or 'businesaios-reliability-lock'), statement_timeout_ms=int(statement_timeout_ms), lock_timeout_ms=int(lock_timeout_ms))
        self._locks_table = safe_sql_identifier(f'{prefix}_distributed_locks')
        self._tokens_table = safe_sql_identifier(f'{prefix}_lock_tokens')
        self._schema_lock = threading.Lock()
        self._schema_ready = False
    def ping(self) -> bool:
        try:
            with self._sessions.open() as session:
                row = session.fetchone('SELECT 1 AS ok;')
                return bool(row and int(row['ok']) == 1)
        except Exception:
            return False
    def _ensure_schema(self) -> None:
        if self._schema_ready: return
        with self._schema_lock:
            if self._schema_ready: return
            with self._sessions.open() as session:
                session.execute(f'CREATE TABLE IF NOT EXISTS {self._tokens_table} (tenant_id TEXT NOT NULL, resource TEXT NOT NULL, last_token BIGINT NOT NULL, updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (tenant_id, resource));')
                session.execute(f'CREATE TABLE IF NOT EXISTS {self._locks_table} (tenant_id TEXT NOT NULL, resource TEXT NOT NULL, owner_id TEXT NOT NULL, fencing_token BIGINT NOT NULL, acquired_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (tenant_id, resource));')
                session.execute(f'CREATE INDEX IF NOT EXISTS idx_{self._locks_table}_expires_at ON {self._locks_table}(expires_at);')
                session.commit()
            self._schema_ready = True
    def _next_token_in_tx(self, *, session: PostgresSession, tenant_id: str, resource: str, now: datetime) -> int:
        row = session.fetchone(f"INSERT INTO {self._tokens_table}(tenant_id, resource, last_token, updated_at) VALUES (%s, %s, 1, %s) ON CONFLICT (tenant_id, resource) DO UPDATE SET last_token = {self._tokens_table}.last_token + 1, updated_at = EXCLUDED.updated_at RETURNING last_token;", (tenant_id, resource, now))
        if row is None:
            raise RuntimeError('failed to allocate fencing token')
        return int(row['last_token'])
    def acquire(self, *, tenant_id: str, resource: str, owner_id: str, ttl_seconds: int = 30, now: datetime | None = None) -> LockLease | None:
        self._ensure_schema()
        tid, res, owner, ttl, moment = normalize_lock_inputs(tenant_id=tenant_id, resource=resource, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)
        expires_at = build_expires_at(now=moment, ttl_seconds=ttl)
        with self._sessions.open() as session:
            try:
                current = session.fetchone(f'SELECT tenant_id, resource, owner_id, fencing_token, acquired_at, expires_at FROM {self._locks_table} WHERE tenant_id=%s AND resource=%s FOR UPDATE;', (tid, res))
                if current is not None and moment < ensure_aware(current['expires_at']):
                    session.rollback(); return None
                token = self._next_token_in_tx(session=session, tenant_id=tid, resource=res, now=moment)
                session.execute(f'INSERT INTO {self._locks_table}(tenant_id, resource, owner_id, fencing_token, acquired_at, expires_at) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (tenant_id, resource) DO UPDATE SET owner_id = EXCLUDED.owner_id, fencing_token = EXCLUDED.fencing_token, acquired_at = EXCLUDED.acquired_at, expires_at = EXCLUDED.expires_at;', (tid, res, owner, token, moment, expires_at))
                session.commit()
            except Exception:
                session.rollback(); raise
        return LockBackendRecord(tenant_id=tid, resource=res, owner_id=owner, fencing_token=token, acquired_at=moment, expires_at=expires_at).to_lease()
    def renew(self, *, lease: LockLease, ttl_seconds: int = 30, now: datetime | None = None) -> LockLease:
        self._ensure_schema(); lease.validate(); ttl = max(1, int(ttl_seconds)); moment = ensure_aware(now or datetime.now(timezone.utc)); expires_at = build_expires_at(now=moment, ttl_seconds=ttl)
        with self._sessions.open() as session:
            try:
                current = session.fetchone(f'SELECT tenant_id, resource, owner_id, fencing_token, acquired_at, expires_at FROM {self._locks_table} WHERE tenant_id=%s AND resource=%s FOR UPDATE;', (lease.tenant_id, lease.resource))
                if current is None: session.rollback(); raise PermissionError('lease no longer exists')
                if str(current['owner_id']) != lease.owner_id: session.rollback(); raise PermissionError('lease ownership mismatch')
                if int(current['fencing_token']) != int(lease.fencing_token): session.rollback(); raise PermissionError('lease fencing token mismatch')
                if moment >= ensure_aware(current['expires_at']): session.rollback(); raise PermissionError('lease has expired')
                session.execute(f'UPDATE {self._locks_table} SET expires_at=%s WHERE tenant_id=%s AND resource=%s AND owner_id=%s AND fencing_token=%s;', (expires_at, lease.tenant_id, lease.resource, lease.owner_id, int(lease.fencing_token)))
                session.commit()
            except Exception:
                session.rollback(); raise
        return LockBackendRecord(tenant_id=lease.tenant_id, resource=lease.resource, owner_id=lease.owner_id, fencing_token=int(lease.fencing_token), acquired_at=ensure_aware(lease.acquired_at), expires_at=expires_at).to_lease()
    def release(self, *, lease: LockLease) -> None:
        self._ensure_schema(); lease.validate()
        with self._sessions.open() as session:
            try:
                session.execute(f'DELETE FROM {self._locks_table} WHERE tenant_id=%s AND resource=%s AND owner_id=%s AND fencing_token=%s;', (lease.tenant_id, lease.resource, lease.owner_id, int(lease.fencing_token)))
                session.commit()
            except Exception:
                session.rollback(); raise
    def get(self, *, tenant_id: str, resource: str) -> LockLease | None:
        self._ensure_schema()
        tid = str(tenant_id).strip()
        res = normalize_resource(resource)
        if not tid:
            raise ValueError('tenant_id is required')
        moment = ensure_aware(datetime.now(timezone.utc))
        with self._sessions.open() as session:
            row = session.fetchone(f'SELECT tenant_id, resource, owner_id, fencing_token, acquired_at, expires_at FROM {self._locks_table} WHERE tenant_id=%s AND resource=%s;', (tid, res))
            if row is None:
                return None
            lease = LockBackendRecord(tenant_id=str(row['tenant_id']), resource=str(row['resource']), owner_id=str(row['owner_id']), fencing_token=int(row['fencing_token']), acquired_at=ensure_aware(row['acquired_at']), expires_at=ensure_aware(row['expires_at'])).to_lease()
            if lease.is_live(now=moment):
                return lease
            try:
                session.execute(f'DELETE FROM {self._locks_table} WHERE tenant_id=%s AND resource=%s AND fencing_token=%s AND expires_at <= %s;', (lease.tenant_id, lease.resource, int(lease.fencing_token), moment))
                session.commit()
            except Exception:
                session.rollback()
            return None
