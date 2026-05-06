from __future__ import annotations

"""Canonical helpers for deterministic idempotency scope generation."""

from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping
import json

from reliability.idempotency_contract import IdempotencyKey

CANON_IDEMPOTENCY_SCOPE = True


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return _normalize_value(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return _normalize_value(asdict(value))
    if isinstance(value, Mapping):
        normalized_items: dict[str, Any] = {}
        for key in sorted(value.keys(), key=lambda item: str(item)):
            normalized_items[str(key)] = _normalize_value(value[key])
        return normalized_items
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, set):
        normalized_items = [_normalize_value(item) for item in value]
        return sorted(normalized_items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def stable_scope_payload(value: Any) -> str:
    normalized = _normalize_value(value)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def hash_scope_seed(*parts: Any) -> str:
    raw_seed = '::'.join(stable_scope_payload(part) for part in parts)
    return sha256(raw_seed.encode('utf-8')).hexdigest()


class IdempotencyScope:
    __slots__ = ('semantic_parts', 'raw_seed', 'scope_hash')

    def __init__(self, *, semantic_parts: tuple[str, ...], raw_seed: str, scope_hash: str) -> None:
        self.semantic_parts = semantic_parts
        self.raw_seed = raw_seed
        self.scope_hash = scope_hash

    @classmethod
    def from_parts(cls, *parts: Any) -> 'IdempotencyScope':
        serialized_parts = tuple(stable_scope_payload(part) for part in parts)
        raw_seed = '::'.join(serialized_parts)
        return cls(
            semantic_parts=serialized_parts,
            raw_seed=raw_seed,
            scope_hash=sha256(raw_seed.encode('utf-8')).hexdigest(),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            'semantic_parts': list(self.semantic_parts),
            'raw_seed': self.raw_seed,
            'scope_hash': self.scope_hash,
        }


def build_idempotency_key(*, tenant_id: str, namespace: str, operation: str, key: str, semantic_scope: Any) -> IdempotencyKey:
    scope = IdempotencyScope.from_parts(semantic_scope)
    idem = IdempotencyKey(
        tenant_id=str(tenant_id),
        namespace=str(namespace),
        operation=str(operation),
        key=str(key),
        scope_hash=scope.scope_hash,
    )
    idem.validate()
    return idem


def build_runtime_request_scope(*, raw_key: str, request_fingerprint: str | None = None, goal: str | None = None, payload: Mapping[str, Any] | None = None) -> IdempotencyScope:
    if str(request_fingerprint or '').strip():
        return IdempotencyScope.from_parts({'request_fingerprint': str(request_fingerprint).strip()})
    if str(goal or '').strip():
        return IdempotencyScope.from_parts({'goal': str(goal).strip()})
    body = dict(payload or {})
    important = {
        'goal': body.get('goal'),
        'business_id': body.get('business_id'),
        'tenant_id': body.get('tenant_id'),
        'step_index': body.get('step_index'),
        'action': body.get('action'),
        'request_fingerprint': body.get('request_fingerprint'),
        'trace_id': body.get('trace_id'),
    }
    non_empty = {key: value for key, value in important.items() if value not in (None, '', [], {}, ())}
    if non_empty:
        return IdempotencyScope.from_parts(non_empty)
    return IdempotencyScope.from_parts({'raw_key': str(raw_key or '').strip()})


def build_evidence_persistence_scope(*, tenant_id: str, business_id: str, run_id: str, step_index: int, persistence_key: str) -> IdempotencyScope:
    return IdempotencyScope.from_parts({
        'tenant_id': str(tenant_id),
        'business_id': str(business_id),
        'run_id': str(run_id),
        'step_index': int(step_index),
        'persistence_key': str(persistence_key),
    })


def build_headless_scope(*, tenant_id: str, namespace: str, operation: str, raw_key: str, payload: Mapping[str, Any] | None = None) -> IdempotencyKey:
    semantic_scope = {
        'tenant_id': str(tenant_id),
        'namespace': str(namespace),
        'operation': str(operation),
        'payload': dict(payload or {}),
    }
    return build_idempotency_key(
        tenant_id=tenant_id,
        namespace=namespace,
        operation=operation,
        key=raw_key,
        semantic_scope=semantic_scope,
    )


__all__ = [
    'CANON_IDEMPOTENCY_SCOPE',
    'IdempotencyScope',
    'build_evidence_persistence_scope',
    'build_headless_scope',
    'build_idempotency_key',
    'build_runtime_request_scope',
    'hash_scope_seed',
    'stable_scope_payload',
]
