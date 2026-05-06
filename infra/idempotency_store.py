from __future__ import annotations

from dataclasses import dataclass, field

from reliability.idempotency_store import InMemoryIdempotencyStore as CanonicalIdempotencyStore
from reliability.idempotency_contract import IdempotencyKey


CANON_INFRA_IDEMPOTENCY_STORE_ADAPTER = True


def _legacy_key(key: str) -> IdempotencyKey:
    normalized = str(key or '').strip()
    if not normalized:
        raise ValueError('key is required')
    return IdempotencyKey(
        tenant_id='unknown_tenant',
        namespace='infra',
        operation='legacy_put_get',
        key=normalized,
        scope_hash='',
    )


@dataclass
class InMemoryIdempotencyStore:
    """Legacy adapter over the canonical reliability idempotency store."""

    _store: CanonicalIdempotencyStore = field(default_factory=CanonicalIdempotencyStore)
    _values: dict[str, object] = field(default_factory=dict)

    def has(self, key: str) -> bool:
        normalized = str(key)
        if normalized in self._values:
            return True
        return self._store.get(key=_legacy_key(key)) is not None

    def get(self, key: str) -> object:
        normalized = str(key)
        if normalized in self._values:
            return self._values[normalized]
        if self._store.get(key=_legacy_key(key)) is None:
            raise KeyError(key)
        raise KeyError(key)

    def put(self, key: str, value: object) -> None:
        ikey = _legacy_key(key)
        owner = 'infra_legacy_adapter'
        decision = self._store.reserve(key=ikey, owner_id=owner)
        resolution = str(decision.resolution.value).strip().lower()
        self._values[str(key)] = value
        if resolution in {'accepted', 'replay_completed', 'rejected_in_progress', 'rejected_terminal_failed'}:
            if resolution == 'accepted':
                self._store.mark_completed(key=ikey, owner_id=owner, result_ref=str(key), metadata_patch={'legacy_value_present': True})
            return
        raise RuntimeError(f'unexpected idempotency resolution: {resolution}')
