from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Sequence

from core.tenancy.normalization import require_tenant_id
from reliability.distributed_lock_backend import (
    DistributedLockBackend,
    LockBackendRecord,
    build_expires_at,
    datetime_to_epoch_ms,
    ensure_aware,
    epoch_ms_to_datetime,
    normalize_lock_inputs,
    normalize_resource,
    normalize_ttl_seconds,
    utc_now,
)
from reliability.distributed_lock_contracts import LockLease


CANON_DISTRIBUTED_LOCK_REDIS = True


class RedisDistributedLockBackend(DistributedLockBackend):
    _ACQUIRE_SCRIPT = """
    local lock_key = KEYS[1]
    local token_key = KEYS[2]
    local tenant_id = ARGV[1]
    local resource = ARGV[2]
    local owner_id = ARGV[3]
    local acquired_ms = tonumber(ARGV[4])
    local expires_ms = tonumber(ARGV[5])
    local ttl_ms = tonumber(ARGV[6])
    if redis.call('EXISTS', lock_key) == 1 then return nil end
    local token = redis.call('INCR', token_key)
    redis.call('HSET', lock_key,
        'tenant_id', tenant_id,
        'resource', resource,
        'owner_id', owner_id,
        'fencing_token', tostring(token),
        'acquired_at_ms', tostring(acquired_ms),
        'expires_at_ms', tostring(expires_ms)
    )
    redis.call('PEXPIRE', lock_key, ttl_ms)
    return { tostring(token), tostring(acquired_ms), tostring(expires_ms) }
    """
    _RENEW_SCRIPT = """
    local lock_key = KEYS[1]
    local owner_id = ARGV[1]
    local fencing_token = ARGV[2]
    local expires_ms = tonumber(ARGV[3])
    local ttl_ms = tonumber(ARGV[4])
    if redis.call('EXISTS', lock_key) == 0 then return { 'MISSING' } end
    local current_owner = redis.call('HGET', lock_key, 'owner_id')
    local current_token = redis.call('HGET', lock_key, 'fencing_token')
    local acquired_ms = redis.call('HGET', lock_key, 'acquired_at_ms')
    if current_owner ~= owner_id then return { 'OWNER_MISMATCH' } end
    if current_token ~= fencing_token then return { 'TOKEN_MISMATCH' } end
    redis.call('HSET', lock_key, 'expires_at_ms', tostring(expires_ms))
    redis.call('PEXPIRE', lock_key, ttl_ms)
    return { tostring(fencing_token), tostring(acquired_ms), tostring(expires_ms) }
    """
    _READ_SCRIPT = """
    local lock_key = KEYS[1]
    if redis.call('EXISTS', lock_key) == 0 then return nil end
    local ttl_ms = redis.call('PTTL', lock_key)
    if ttl_ms == -1 then return { 'NO_EXPIRY' } end
    if ttl_ms < 1 then return nil end
    local values = redis.call('HMGET', lock_key,
        'tenant_id',
        'resource',
        'owner_id',
        'fencing_token',
        'acquired_at_ms'
    )
    return {
        values[1], values[2], values[3], values[4], values[5], tostring(ttl_ms)
    }
    """
    _RELEASE_SCRIPT = """
    local lock_key = KEYS[1]
    local owner_id = ARGV[1]
    local fencing_token = ARGV[2]
    if redis.call('EXISTS', lock_key) == 0 then return 0 end
    local current_owner = redis.call('HGET', lock_key, 'owner_id')
    local current_token = redis.call('HGET', lock_key, 'fencing_token')
    if current_owner == owner_id and current_token == fencing_token then
        redis.call('DEL', lock_key)
        return 1
    end
    return 0
    """

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        client: Any | None = None,
        key_prefix: str = "businesaios:reliability:lock",
    ) -> None:
        self._redis_url = str(redis_url or "").strip()
        self._client = client
        self._key_prefix = str(key_prefix or "").strip()
        if not self._key_prefix:
            raise ValueError("key_prefix is required")
        self._registration_lock = Lock()
        self._scripts_registered = False

    @staticmethod
    def _text(value: object) -> str:
        if value is None:
            raise RuntimeError("redis lock response contains a missing value")
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeError as exc:
                raise RuntimeError("redis lock response is not UTF-8") from exc
        return str(value)

    @classmethod
    def _result_values(cls, result: object) -> tuple[str, ...]:
        if not isinstance(result, Sequence) or isinstance(result, (str, bytes)):
            raise RuntimeError("redis lock script returned an invalid result")
        return tuple(cls._text(value) for value in result)

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._redis_url:
            raise ValueError("redis_url is required when client is not provided")
        try:
            import redis  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "RedisDistributedLockBackend requires the `redis` package"
            ) from exc
        self._client = redis.Redis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        return self._client

    def _register_scripts(self) -> None:
        if self._scripts_registered:
            return
        with self._registration_lock:
            if self._scripts_registered:
                return
            client = self._ensure_client()
            acquire = client.register_script(self._ACQUIRE_SCRIPT)
            renew = client.register_script(self._RENEW_SCRIPT)
            read = client.register_script(self._READ_SCRIPT)
            release = client.register_script(self._RELEASE_SCRIPT)
            self._acquire_script = acquire
            self._renew_script = renew
            self._read_script = read
            self._release_script = release
            self._scripts_registered = True

    def _lock_key(self, tenant_id: str, resource: str) -> str:
        return f"{self._key_prefix}:{tenant_id}:{resource}"

    def _token_key(self, tenant_id: str, resource: str) -> str:
        return f"{self._key_prefix}:token:{tenant_id}:{resource}"

    def ping(self) -> bool:
        try:
            return bool(self._ensure_client().ping())
        except Exception:
            return False

    def acquire(
        self,
        *,
        tenant_id: str,
        resource: str,
        owner_id: str,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease | None:
        tid, res, owner, ttl, moment = normalize_lock_inputs(
            tenant_id=tenant_id,
            resource=resource,
            owner_id=owner_id,
            ttl_seconds=ttl_seconds,
            now=now,
        )
        expires_at = build_expires_at(now=moment, ttl_seconds=ttl)
        self._register_scripts()
        result = self._acquire_script(
            keys=[self._lock_key(tid, res), self._token_key(tid, res)],
            args=[
                tid,
                res,
                owner,
                str(datetime_to_epoch_ms(moment)),
                str(datetime_to_epoch_ms(expires_at)),
                str(ttl * 1000),
            ],
        )
        if not result:
            return None
        values = self._result_values(result)
        if len(values) != 3:
            raise RuntimeError("redis acquire script returned an invalid result")
        return LockBackendRecord(
            tenant_id=tid,
            resource=res,
            owner_id=owner,
            fencing_token=int(values[0]),
            acquired_at=epoch_ms_to_datetime(values[1]),
            expires_at=epoch_ms_to_datetime(values[2]),
        ).to_lease()

    def renew(
        self,
        *,
        lease: LockLease,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease:
        lease.validate()
        ttl = normalize_ttl_seconds(ttl_seconds)
        moment = ensure_aware(now or utc_now())
        expires_at = build_expires_at(now=moment, ttl_seconds=ttl)
        self._register_scripts()
        result = self._renew_script(
            keys=[self._lock_key(lease.tenant_id, lease.resource)],
            args=[
                lease.owner_id,
                str(lease.fencing_token),
                str(datetime_to_epoch_ms(expires_at)),
                str(ttl * 1000),
            ],
        )
        if not result:
            raise PermissionError("lease no longer exists")
        values = self._result_values(result)
        marker = values[0]
        if marker == "MISSING":
            raise PermissionError("lease no longer exists")
        if marker == "OWNER_MISMATCH":
            raise PermissionError("lease ownership mismatch")
        if marker == "TOKEN_MISMATCH":
            raise PermissionError("lease fencing token mismatch")
        if len(values) != 3:
            raise RuntimeError("redis renew script returned an invalid result")
        returned_token = int(values[0])
        if returned_token != int(lease.fencing_token):
            raise RuntimeError("redis renew script changed the fencing token")
        return LockBackendRecord(
            tenant_id=lease.tenant_id,
            resource=lease.resource,
            owner_id=lease.owner_id,
            fencing_token=returned_token,
            acquired_at=epoch_ms_to_datetime(values[1]),
            expires_at=epoch_ms_to_datetime(values[2]),
        ).to_lease()

    def release(self, *, lease: LockLease) -> None:
        lease.validate()
        self._register_scripts()
        self._release_script(
            keys=[self._lock_key(lease.tenant_id, lease.resource)],
            args=[lease.owner_id, str(lease.fencing_token)],
        )

    def get(self, *, tenant_id: str, resource: str) -> LockLease | None:
        tid = require_tenant_id(tenant_id)
        res = normalize_resource(resource)
        self._register_scripts()
        result = self._read_script(
            keys=[self._lock_key(tid, res)],
            args=[],
        )
        if not result:
            return None
        values = self._result_values(result)
        if values == ("NO_EXPIRY",):
            raise RuntimeError("redis lock key has no expiry")
        if len(values) != 6:
            raise RuntimeError("redis read script returned an invalid result")
        try:
            ttl_ms = int(values[5])
            if ttl_ms <= 0:
                return None
            if values[0] != tid or values[1] != res:
                raise ValueError("redis lock payload identity mismatch")
            stored_acquired_at = epoch_ms_to_datetime(values[4])
            read_at = ensure_aware(utc_now())
            expires_at = read_at + timedelta(milliseconds=ttl_ms)
            acquired_at = min(stored_acquired_at, read_at)
            return LockBackendRecord(
                tenant_id=values[0],
                resource=values[1],
                owner_id=values[2],
                fencing_token=int(values[3]),
                acquired_at=acquired_at,
                expires_at=expires_at,
            ).to_lease()
        except (TypeError, ValueError) as exc:
            raise RuntimeError("redis lock payload is invalid") from exc



__all__ = [
    "CANON_DISTRIBUTED_LOCK_REDIS",
    "RedisDistributedLockBackend",
]
