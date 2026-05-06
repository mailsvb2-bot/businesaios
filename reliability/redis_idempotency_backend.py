from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from reliability.distributed_idempotency_backend import DistributedIdempotencyStore

CANON_REDIS_IDEMPOTENCY_BACKEND = True


class RedisClientProtocol(Protocol):
    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> Any: ...
    def get(self, key: str) -> Any: ...
    def incr(self, key: str) -> int: ...
    def ttl(self, key: str) -> int: ...
    def delete(self, key: str) -> int: ...
    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any: ...


@dataclass(frozen=True)
class RedisIdempotencyConfig:
    redis_url: str
    token: str | None = None
    key_prefix: str = 'businesaios:idempotency'
    default_ttl_seconds: int = 1200

    def validate(self) -> None:
        if not str(self.redis_url or '').strip():
            raise ValueError('redis_url is required')
        if self.default_ttl_seconds < 60:
            raise ValueError('default_ttl_seconds must be >= 60')


class RedisCompareAndSwapPort:
    def __init__(self, *, client: RedisClientProtocol, default_ttl_seconds: int = 1200) -> None:
        self._client = client
        self._default_ttl_seconds = max(60, int(default_ttl_seconds))

    def create_if_absent(self, *, key: str, payload: Mapping[str, Any], ttl_seconds: int | None = None) -> bool:
        body = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
        result = self._client.set(key, body, nx=True, ex=int(ttl_seconds or self._default_ttl_seconds))
        return bool(result)

    def read(self, *, key: str) -> Mapping[str, Any] | None:
        raw = self._client.get(key)
        if raw in {None, b'', ''}:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        return dict(json.loads(str(raw)))

    def compare_and_swap(self, *, key: str, expected_version: int, payload: Mapping[str, Any], ttl_seconds: int | None = None) -> bool:
        script = (
            "local current = redis.call('GET', KEYS[1]);"
            "if not current then return 0 end;"
            "local decoded = cjson.decode(current);"
            "if tonumber(decoded['version'] or 0) ~= tonumber(ARGV[1]) then return 0 end;"
            "redis.call('SET', KEYS[1], ARGV[2], 'EX', tonumber(ARGV[3]));"
            "return 1;"
        )
        body = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
        result = self._client.eval(script, 1, key, int(expected_version), body, int(ttl_seconds or self._default_ttl_seconds))
        return int(result or 0) == 1


class RedisSequencePort:
    def __init__(self, *, client: RedisClientProtocol, prefix: str = 'businesaios:sequence') -> None:
        self._client = client
        self._prefix = str(prefix).strip(':')

    def next_value(self, *, namespace: str) -> int:
        return int(self._client.incr(f'{self._prefix}:{namespace}'))


@dataclass(frozen=True)
class RedisIdempotencyBackend:
    client: RedisClientProtocol
    config: RedisIdempotencyConfig

    def __post_init__(self) -> None:
        self.config.validate()

    def build_store(self) -> DistributedIdempotencyStore:
        return DistributedIdempotencyStore(
            cas=RedisCompareAndSwapPort(client=self.client, default_ttl_seconds=self.config.default_ttl_seconds),
            sequence=RedisSequencePort(client=self.client, prefix=f'{self.config.key_prefix}:sequence'),
            key_prefix=self.config.key_prefix,
        )

    def healthcheck(self, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {'status': 'ready_for_credentials', 'backend': 'redis', 'key_prefix': self.config.key_prefix}
        probe_key = f'{self.config.key_prefix}:health'
        self.client.set(probe_key, '1', ex=60)
        return {'status': 'ok' if self.client.get(probe_key) else 'degraded', 'backend': 'redis', 'key_prefix': self.config.key_prefix}
