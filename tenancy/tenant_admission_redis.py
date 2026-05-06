from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_admission_contract import (
    TenantAdmissionBackend,
    TenantAdmissionLease,
    TenantAdmissionRequest,
    TenantAdmissionVerdict,
)


CANON_TENANT_ADMISSION_REDIS = True


class RedisTenantAdmissionBackend(TenantAdmissionBackend):
    """Redis-backed distributed admission.

    Notes:
    - all state-mutating operations use Lua for atomicity;
    - the active ZSET is intentionally not TTL-bound per lease, because a short-ttl
      refresh on one run must not accidentally expire the whole tenant active set;
    - stale entries are removed on every read/write path.
    """

    def __init__(self, *, redis_url: str, key_prefix: str = "businesaios:tenant_admission") -> None:
        redis_url = str(redis_url or "").strip()
        if not redis_url:
            raise ValueError("redis_url is required")
        prefix = str(key_prefix or "").strip() or "businesaios:tenant_admission"
        if " " in prefix:
            raise ValueError("key_prefix must not contain spaces")
        self._key_prefix = prefix
        try:
            import redis
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("redis package is required for RedisTenantAdmissionBackend") from exc
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def admit(self, *, request: TenantAdmissionRequest, limit: int) -> TenantAdmissionVerdict:
        request.validate()
        max_active = max(0, int(limit))
        ttl_seconds = int(request.ttl_seconds)
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        tenant_key = self._tenant_key(request.tenant_id)
        lease_key = self._lease_key(request.tenant_id, request.run_id)
        active_key = tenant_key + ":active"
        token_key = tenant_key + ":fencing"
        labels_json = json.dumps(dict(request.labels), sort_keys=True, separators=(",", ":"))
        requested_at = request.requested_at.astimezone(timezone.utc)
        expires_at = requested_at + timedelta(seconds=ttl_seconds)
        housekeeping_ttl = max(ttl_seconds * 4, 3600)

        script = """
        local lease_key = KEYS[1]
        local active_key = KEYS[2]
        local token_key = KEYS[3]
        local now_score = tonumber(ARGV[1])
        local expires_score = tonumber(ARGV[2])
        local ttl = tonumber(ARGV[3])
        local active_ttl = tonumber(ARGV[4])
        local limit = tonumber(ARGV[5])
        local run_id = ARGV[6]
        local owner_id = ARGV[7]
        local labels_json = ARGV[8]
        local tenant_id = ARGV[9]
        local acquired_at = ARGV[10]
        local expires_at = ARGV[11]

        redis.call('ZREMRANGEBYSCORE', active_key, '-inf', now_score)
        local existing = redis.call('HGETALL', lease_key)
        if #existing > 0 then
            local existing_owner = redis.call('HGET', lease_key, 'owner_id')
            local existing_labels = redis.call('HGET', lease_key, 'labels_json')
            local existing_acquired_at = redis.call('HGET', lease_key, 'acquired_at')
            if existing_owner ~= owner_id then
                return {0, 'lease_owned_by_another_owner', redis.call('ZCARD', active_key), ''}
            end
            if existing_labels ~= labels_json then
                return {0, 'lease_labels_mismatch', redis.call('ZCARD', active_key), ''}
            end
            redis.call('HSET', lease_key,
                'tenant_id', tenant_id,
                'run_id', run_id,
                'owner_id', owner_id,
                'heartbeat_at', acquired_at,
                'expires_at', expires_at,
                'labels_json', labels_json,
                'acquired_at', existing_acquired_at
            )
            redis.call('EXPIRE', lease_key, ttl)
            redis.call('ZADD', active_key, expires_score, run_id)
            redis.call('EXPIRE', active_key, active_ttl)
            return {1, 'already_acquired', redis.call('ZCARD', active_key), redis.call('HGET', lease_key, 'fencing_token'), existing_acquired_at}
        end

        local active_count = redis.call('ZCARD', active_key)
        if limit <= 0 then
            return {0, 'tenant_runtime_disabled', active_count, '', ''}
        end
        if active_count >= limit then
            return {0, 'tenant_runtime_capacity_exceeded', active_count, '', ''}
        end

        local token = redis.call('INCR', token_key)
        redis.call('HMSET', lease_key,
            'tenant_id', tenant_id,
            'run_id', run_id,
            'owner_id', owner_id,
            'fencing_token', tostring(token),
            'acquired_at', acquired_at,
            'heartbeat_at', acquired_at,
            'expires_at', expires_at,
            'labels_json', labels_json
        )
        redis.call('EXPIRE', lease_key, ttl)
        redis.call('ZADD', active_key, expires_score, run_id)
        redis.call('EXPIRE', active_key, active_ttl)
        return {1, 'acquired', redis.call('ZCARD', active_key), tostring(token), acquired_at}
        """

        allowed, reason, active_runs, token, acquired_at_iso = self._redis.eval(
            script,
            3,
            lease_key,
            active_key,
            token_key,
            str(requested_at.timestamp()),
            str(expires_at.timestamp()),
            str(ttl_seconds),
            str(housekeeping_ttl),
            str(max_active),
            request.run_id,
            request.owner_id,
            labels_json,
            request.tenant_id,
            requested_at.isoformat(),
            expires_at.isoformat(),
        )
        lease = None
        if int(allowed) == 1:
            lease = TenantAdmissionLease(
                tenant_id=request.tenant_id,
                run_id=request.run_id,
                owner_id=request.owner_id,
                fencing_token=int(token),
                acquired_at=datetime.fromisoformat(str(acquired_at_iso)).astimezone(timezone.utc),
                expires_at=expires_at,
            )
            lease.validate()
        return TenantAdmissionVerdict(bool(int(allowed)), str(reason), request.tenant_id, request.run_id, int(active_runs), max_active, lease)

    def renew(self, *, tenant_id: str, run_id: str, owner_id: str, ttl_seconds: int) -> TenantAdmissionLease:
        tid = require_tenant_id(tenant_id)
        rid = str(run_id or "").strip()
        oid = str(owner_id or "").strip()
        ttl = int(ttl_seconds)
        if not rid or not oid:
            raise ValueError("run_id and owner_id are required")
        if ttl <= 0:
            raise ValueError("ttl_seconds must be > 0")
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl)
        active_ttl = max(ttl * 4, 3600)
        script = """
        local lease_key = KEYS[1]
        local active_key = KEYS[2]
        local now_score = tonumber(ARGV[1])
        local expires_score = tonumber(ARGV[2])
        local ttl = tonumber(ARGV[3])
        local active_ttl = tonumber(ARGV[4])
        local owner_id = ARGV[5]
        local run_id = ARGV[6]
        local heartbeat_at = ARGV[7]
        local expires_at = ARGV[8]

        redis.call('ZREMRANGEBYSCORE', active_key, '-inf', now_score)
        local existing = redis.call('HGETALL', lease_key)
        if #existing == 0 then
            return {0, 'missing', '', '', ''}
        end
        local existing_owner = redis.call('HGET', lease_key, 'owner_id')
        if existing_owner ~= owner_id then
            return {0, 'owner_mismatch', '', '', ''}
        end
        redis.call('HSET', lease_key, 'heartbeat_at', heartbeat_at, 'expires_at', expires_at)
        redis.call('EXPIRE', lease_key, ttl)
        redis.call('ZADD', active_key, expires_score, run_id)
        redis.call('EXPIRE', active_key, active_ttl)
        return {1, redis.call('HGET', lease_key, 'fencing_token'), redis.call('HGET', lease_key, 'acquired_at'), expires_at, owner_id}
        """
        status, token, acquired_at_iso, expires_at_iso, returned_owner = self._redis.eval(
            script,
            2,
            self._lease_key(tid, rid),
            self._tenant_key(tid) + ":active",
            str(now.timestamp()),
            str(expires_at.timestamp()),
            str(ttl),
            str(active_ttl),
            oid,
            rid,
            now.isoformat(),
            expires_at.isoformat(),
        )
        if int(status) == 0 and str(token) == 'missing':
            raise KeyError(f"missing tenant admission lease: tenant={tid} run_id={rid}")
        if int(status) == 0 and str(token) == 'owner_mismatch':
            raise PermissionError(f"tenant admission lease owner mismatch: tenant={tid} run_id={rid}")
        lease = TenantAdmissionLease(
            tenant_id=tid,
            run_id=rid,
            owner_id=str(returned_owner),
            fencing_token=int(token),
            acquired_at=datetime.fromisoformat(str(acquired_at_iso)).astimezone(timezone.utc),
            expires_at=datetime.fromisoformat(str(expires_at_iso)).astimezone(timezone.utc),
        )
        lease.validate()
        return lease

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool:
        tid = require_tenant_id(tenant_id)
        rid = str(run_id or "").strip()
        oid = str(owner_id or "").strip()
        if not rid or not oid:
            raise ValueError("run_id and owner_id are required")
        script = """
        local lease_key = KEYS[1]
        local active_key = KEYS[2]
        local owner_id = ARGV[1]
        local run_id = ARGV[2]
        local payload = redis.call('HGETALL', lease_key)
        if #payload == 0 then
            return {0, 'missing'}
        end
        local existing_owner = redis.call('HGET', lease_key, 'owner_id')
        if existing_owner ~= owner_id then
            return {0, 'owner_mismatch'}
        end
        redis.call('DEL', lease_key)
        redis.call('ZREM', active_key, run_id)
        return {1, 'released'}
        """
        released, reason = self._redis.eval(
            script,
            2,
            self._lease_key(tid, rid),
            self._tenant_key(tid) + ":active",
            oid,
            rid,
        )
        if int(released) == 0 and str(reason) == 'owner_mismatch':
            raise PermissionError(f"tenant admission lease owner mismatch: tenant={tid} run_id={rid}")
        return bool(int(released))

    def list_active(self, *, tenant_id: str) -> tuple[TenantAdmissionLease, ...]:
        tid = require_tenant_id(tenant_id)
        active_key = self._tenant_key(tid) + ":active"
        now = datetime.now(timezone.utc)
        script = """
        local active_key = KEYS[1]
        local lease_prefix = ARGV[1]
        local now_score = tonumber(ARGV[2])
        redis.call('ZREMRANGEBYSCORE', active_key, '-inf', now_score)
        local run_ids = redis.call('ZRANGE', active_key, 0, -1)
        local out = {}
        for _, run_id in ipairs(run_ids) do
            local payload = redis.call('HGETALL', lease_prefix .. run_id)
            if #payload == 0 then
                redis.call('ZREM', active_key, run_id)
            else
                local map = {}
                for i = 1, #payload, 2 do
                    map[payload[i]] = payload[i + 1]
                end
                table.insert(out, run_id)
                table.insert(out, map['owner_id'])
                table.insert(out, map['fencing_token'])
                table.insert(out, map['acquired_at'])
                table.insert(out, map['expires_at'])
            end
        end
        return out
        """
        raw = self._redis.eval(script, 1, active_key, self._lease_key(tid, ''), str(now.timestamp()))
        leases: list[TenantAdmissionLease] = []
        for index in range(0, len(raw), 5):
            run_id, owner_id, fencing_token, acquired_at_iso, expires_at_iso = raw[index:index + 5]
            lease = TenantAdmissionLease(
                tenant_id=tid,
                run_id=str(run_id),
                owner_id=str(owner_id),
                fencing_token=int(fencing_token),
                acquired_at=datetime.fromisoformat(str(acquired_at_iso)).astimezone(timezone.utc),
                expires_at=datetime.fromisoformat(str(expires_at_iso)).astimezone(timezone.utc),
            )
            lease.validate()
            leases.append(lease)
        return tuple(sorted(leases, key=lambda item: (item.acquired_at, item.run_id)))

    def _tenant_key(self, tenant_id: str) -> str:
        return f"{self._key_prefix}:{require_tenant_id(tenant_id)}"

    def _lease_key(self, tenant_id: str, run_id: str) -> str:
        rid = str(run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        return f"{self._tenant_key(tenant_id)}:lease:{rid}"


__all__ = ["CANON_TENANT_ADMISSION_REDIS", "RedisTenantAdmissionBackend"]
