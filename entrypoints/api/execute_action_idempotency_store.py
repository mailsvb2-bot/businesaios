from __future__ import annotations
CANON_EXECUTE_ACTION_IDEMPOTENCY_STORE_FINAL_OWNER = True


from dataclasses import dataclass
from typing import Any, Protocol

from entrypoints.api.action_models import ExecuteActionResponse
from reliability.idempotency_contract import IdempotencyDecision, IdempotencyResolution, IdempotencyState
from reliability.idempotency_scope import build_idempotency_key
from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore
from reliability.idempotency_store import InMemoryIdempotencyStore as ReliabilityInMemoryIdempotencyStore


CANON_API_EXECUTE_ACTION_IDEMPOTENCY_STORE = True


class ReliabilityStoreLike(Protocol):
    def get(self, *, key: object) -> object | None: ...

    def reserve(self, *, key: object, owner_id: str, metadata_patch: dict[str, Any] | None = None) -> IdempotencyDecision: ...

    def mark_completed(self, *, key: object, owner_id: str, metadata_patch: dict[str, Any] | None = None) -> object: ...

    def mark_failed(self, *, key: object, owner_id: str, reason: str | None = None, metadata_patch: dict[str, Any] | None = None) -> object: ...


@dataclass(frozen=True)
class DurableExecuteActionIdempotencyStore:
    """
    Adapter bridge from the simple has/get/put executor contract used by the API
    reliability envelope to the durable SQLite-backed idempotency store.

    This is infra-only. It persists canonical execute-action API responses without
    introducing a second execution policy path.
    """

    store: ReliabilityStoreLike
    tenant_id: str = 'api'
    namespace: str = 'interfaces.api'
    operation: str = 'execute_action'
    owner_id: str = 'api-execute-action-idempotency'

    def status(self, key: str) -> str:
        record = self.store.get(key=self._build_key(key))
        if record is None:
            return 'missing'
        payload = self._response_payload(record)
        if record.state is IdempotencyState.COMPLETED and payload is not None:
            return 'completed'
        if record.state is IdempotencyState.FAILED:
            return 'terminal_failed'
        if record.has_live_lease():
            return 'in_progress'
        return 'missing'

    def has(self, key: str) -> bool:
        return self.status(key) == 'completed'

    def get(self, key: str) -> ExecuteActionResponse:
        record = self.store.get(key=self._build_key(key))
        if record is None:
            raise KeyError(key)
        payload = self._response_payload(record)
        if payload is None:
            raise KeyError(key)
        return ExecuteActionResponse.model_validate(payload)

    def put(self, key: str, value: object) -> None:
        response = self._normalize_response(value)
        idem_key = self._build_key(key)
        decision = self.store.reserve(
            key=idem_key,
            owner_id=self.owner_id,
            metadata_patch={
                'surface': 'execute_action_api',
                'storage_key': str(key),
            },
        )
        if decision.resolution not in {IdempotencyResolution.ACCEPTED, IdempotencyResolution.REPLAY_COMPLETED}:
            raise RuntimeError(f'unexpected idempotency resolution for completed response persistence: {decision.resolution.value}')
        self.store.mark_completed(
            key=idem_key,
            owner_id=self.owner_id,
            metadata_patch={
                'surface': 'execute_action_api',
                'storage_key': str(key),
                'response_payload': response.model_dump(mode='python'),
            },
        )

    def reserve(self, key: str) -> IdempotencyDecision:
        return self.store.reserve(
            key=self._build_key(key),
            owner_id=self.owner_id,
            metadata_patch={
                'surface': 'execute_action_api',
                'storage_key': str(key),
            },
        )

    def mark_completed(self, key: str, value: object) -> None:
        response = self._normalize_response(value)
        self.store.mark_completed(
            key=self._build_key(key),
            owner_id=self.owner_id,
            metadata_patch={
                'surface': 'execute_action_api',
                'storage_key': str(key),
                'response_payload': response.model_dump(mode='python'),
            },
        )

    def mark_failed(self, key: str, *, reason: str | None = None) -> None:
        self.store.mark_failed(
            key=self._build_key(key),
            owner_id=self.owner_id,
            reason=reason,
            metadata_patch={
                'surface': 'execute_action_api',
                'storage_key': str(key),
            },
        )

    def _build_key(self, key: str):
        text = str(key or '').strip()
        if not text:
            raise ValueError('idempotency key is required')
        return build_idempotency_key(
            tenant_id=str(self.tenant_id),
            namespace=str(self.namespace),
            operation=str(self.operation),
            key=text,
            semantic_scope={'storage_key': text},
        )

    @staticmethod
    def _normalize_response(value: object) -> ExecuteActionResponse:
        if isinstance(value, ExecuteActionResponse):
            return value
        if hasattr(value, 'model_dump'):
            return ExecuteActionResponse.model_validate(value.model_dump(mode='python'))
        if isinstance(value, dict):
            return ExecuteActionResponse.model_validate(value)
        return ExecuteActionResponse.model_validate({
            'status': getattr(value, 'status'),
            'action_type': getattr(value, 'action_type'),
            'reason': getattr(value, 'reason', None),
            'details': getattr(value, 'details', {}),
            'capability_view': getattr(value, 'capability_view', {}),
        })

    @staticmethod
    def _response_payload(record: object) -> dict[str, Any] | None:
        metadata = dict(getattr(record, 'metadata', {}) or {})
        payload = metadata.get('response_payload')
        return dict(payload) if isinstance(payload, dict) else None


def build_api_execute_action_idempotency_store(candidate: object | None):
    if isinstance(candidate, (SQLiteIdempotencyStore, ReliabilityInMemoryIdempotencyStore)):
        return DurableExecuteActionIdempotencyStore(store=candidate)
    if candidate is not None and all(hasattr(candidate, attr) for attr in ('reserve', 'get', 'mark_completed', 'mark_failed')):
        return DurableExecuteActionIdempotencyStore(store=candidate)
    if candidate is not None and all(hasattr(candidate, attr) for attr in ('has', 'get', 'put')):
        return candidate
    return None


__all__ = [
    'CANON_API_EXECUTE_ACTION_IDEMPOTENCY_STORE',
    'DurableExecuteActionIdempotencyStore',
    'build_api_execute_action_idempotency_store',
]
