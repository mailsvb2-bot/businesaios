from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from core.tenancy.normalization import require_tenant_id
from reliability.idempotency_contract import IdempotencyResolution, IdempotencyStore
from reliability.idempotency_scope import build_idempotency_key
from runtime.queue.backpressure_policy import BackpressurePolicy
from runtime.queue.job_contract import JobDispatchRequest, JobRecord, JobState, normalize_now
from runtime.queue.job_store import JobStore
from runtime.queue.rate_limit_guard import RateLimitGuard, RateLimitVerdict
from tenancy.tenant_contract import TenantRegistryContract
from tenancy.tenant_queue_scope import TenantQueueScope

CANON_RUNTIME_QUEUE_DISPATCHER = True


@dataclass(frozen=True)
class DispatchVerdict:
    accepted: bool
    job: JobRecord | None
    reason: str
    retry_after_seconds: int = 0
    idempotency_resolution: str | None = None


class JobDispatcher:
    """Admits jobs into the runtime queue.

    This module is an edge adapter only. It never decides *what* the
    business should do; it only persists already-authorized work.
    """

    def __init__(
        self,
        *,
        store: JobStore,
        rate_limit_guard: RateLimitGuard | None = None,
        backpressure_policy: BackpressurePolicy | None = None,
        idempotency_store: IdempotencyStore | None = None,
        idempotency_namespace: str = 'runtime_queue',
        idempotency_operation: str = 'dispatch_job',
        idempotency_owner_id: str = 'runtime-queue-dispatcher',
        tenant_registry: TenantRegistryContract | None = None,
    ) -> None:
        self._store = store
        self._rate_limit_guard = rate_limit_guard or RateLimitGuard()
        self._backpressure_policy = backpressure_policy or BackpressurePolicy()
        self._idempotency_store = idempotency_store
        self._idempotency_namespace = str(idempotency_namespace or 'runtime_queue')
        self._idempotency_operation = str(idempotency_operation or 'dispatch_job')
        self._idempotency_owner_id = str(idempotency_owner_id or 'runtime-queue-dispatcher')
        self._tenant_registry = tenant_registry

    def dispatch(self, request: JobDispatchRequest) -> DispatchVerdict:
        scope = self._scope_for_request(request)
        request = self._canonicalize_request(scope=scope, request=request)
        self._assert_tenant_isolation(scope=scope, request=request)
        existing = self._store.get_by_dedupe_key(tenant_id=request.tenant_id, dedupe_key=request.dedupe_key)
        if existing is not None and existing.state not in {JobState.FAILED, JobState.DEAD_LETTER, JobState.CANCELLED}:
            return DispatchVerdict(True, existing, 'dedupe_existing', 0, 'store_existing')

        idempotency_decision = self._reserve_idempotency(request=request)
        if idempotency_decision is not None and idempotency_decision.resolution is not IdempotencyResolution.ACCEPTED:
            replayed = self._store.get_by_dedupe_key(tenant_id=request.tenant_id, dedupe_key=request.dedupe_key)
            return DispatchVerdict(
                replayed is not None,
                replayed,
                'idempotency_replay' if replayed is not None else 'idempotency_rejected',
                0,
                idempotency_decision.resolution.value,
            )

        rate_limit = self._rate_limit_guard.evaluate(tenant_id=request.tenant_id, queue_name=request.queue_name, now=normalize_now())
        if not rate_limit.allowed:
            return self._rate_limited(rate_limit, idempotency_decision=idempotency_decision)

        queue_depth = self._store.count(tenant_id=request.tenant_id, queue_name=request.queue_name, state=JobState.PENDING)
        claimed_depth = self._store.count(tenant_id=request.tenant_id, queue_name=request.queue_name, state=JobState.CLAIMED)
        pressure = self._backpressure_policy.evaluate(queue_depth=queue_depth, claimed_depth=claimed_depth)
        if not pressure.allowed:
            return DispatchVerdict(False, None, pressure.reason, int(pressure.suggested_delay_seconds), self._resolution_value(idempotency_decision))

        stored = self._store.put(request.to_record())
        if stored.job_id != request.job_id and stored.dedupe_key == request.dedupe_key:
            return DispatchVerdict(True, stored, 'dedupe_existing', 0, self._resolution_value(idempotency_decision))
        self._mark_idempotency_completed(request=request, stored=stored)
        return DispatchVerdict(True, stored, 'accepted', int(pressure.suggested_delay_seconds), self._resolution_value(idempotency_decision))

    def _reserve_idempotency(self, *, request: JobDispatchRequest):
        if self._idempotency_store is None:
            return None
        scope = self._scope_for_request(request)
        key = build_idempotency_key(
            tenant_id=request.tenant_id,
            namespace=self._idempotency_namespace,
            operation=self._idempotency_operation,
            key=request.dedupe_key,
            semantic_scope={
                'queue_scope': scope.scope_key,
                'qualified_job_id': scope.qualify_job_id(request.job_id),
                'qualified_dedupe_key': scope.qualify_dedupe_key(request.dedupe_key),
                'queue_name': request.queue_name,
                'job_type': request.job_type,
                'payload': dict(request.payload),
                'priority': int(request.priority),
                'delay_seconds': int(request.delay_seconds),
                'max_attempts': int(request.max_attempts),
            },
        )
        return self._idempotency_store.reserve(
            key=key,
            owner_id=self._idempotency_owner_id,
            metadata_patch={'job_id': request.job_id, 'queue_name': request.queue_name, 'job_type': request.job_type},
        )

    def _mark_idempotency_completed(self, *, request: JobDispatchRequest, stored: JobRecord) -> None:
        if self._idempotency_store is None:
            return
        scope = self._scope_for_request(request)
        key = build_idempotency_key(
            tenant_id=request.tenant_id,
            namespace=self._idempotency_namespace,
            operation=self._idempotency_operation,
            key=request.dedupe_key,
            semantic_scope={
                'queue_scope': scope.scope_key,
                'qualified_job_id': scope.qualify_job_id(request.job_id),
                'qualified_dedupe_key': scope.qualify_dedupe_key(request.dedupe_key),
                'queue_name': request.queue_name,
                'job_type': request.job_type,
                'payload': dict(request.payload),
                'priority': int(request.priority),
                'delay_seconds': int(request.delay_seconds),
                'max_attempts': int(request.max_attempts),
            },
        )
        self._idempotency_store.mark_completed(
            key=key,
            owner_id=self._idempotency_owner_id,
            result_ref=stored.job_id,
            result_digest=stored.job_id,
            metadata_patch={'job_state': stored.state.value, 'queue_name': stored.queue_name},
        )


    @staticmethod
    def _canonicalize_request(*, scope: TenantQueueScope, request: JobDispatchRequest) -> JobDispatchRequest:
        payload = dict(request.payload) if isinstance(request.payload, Mapping) else {}
        payload.setdefault('tenant_id', request.tenant_id)
        payload.setdefault('queue_name', request.queue_name)
        payload['qualified_job_id'] = scope.qualify_job_id(request.job_id)
        payload['qualified_dedupe_key'] = scope.qualify_dedupe_key(request.dedupe_key)
        payload.setdefault('tenant_queue_scope', {
            'tenant_id': scope.tenant_id,
            'queue_name': scope.queue_name,
            'namespace': scope.namespace,
            'scope_key': scope.scope_key,
        })
        return replace(request, payload=payload)

    @staticmethod
    def _scope_for_request(request: JobDispatchRequest) -> TenantQueueScope:
        payload = dict(request.payload) if isinstance(request.payload, Mapping) else {}
        raw_scope = payload.get('tenant_queue_scope') if isinstance(payload.get('tenant_queue_scope'), Mapping) else payload.get('tenant_scope') if isinstance(payload.get('tenant_scope'), Mapping) else {}
        namespace = str(raw_scope.get('namespace') or 'runtime').strip() or 'runtime'
        return TenantQueueScope(
            tenant_id=require_tenant_id(request.tenant_id),
            queue_name=request.queue_name,
            namespace=namespace,
        )

    def _assert_tenant_isolation(self, *, scope: TenantQueueScope, request: JobDispatchRequest) -> None:
        scope.validate()
        if self._tenant_registry is not None and hasattr(self._tenant_registry, 'assert_active'):
            self._tenant_registry.assert_active(scope.tenant_id)
        payload = dict(request.payload) if isinstance(request.payload, Mapping) else {}
        if payload.get('tenant_id') is not None or payload.get('queue_name') is not None:
            scope.assert_job_mapping({
                'tenant_id': payload.get('tenant_id', request.tenant_id),
                'queue_name': payload.get('queue_name', request.queue_name),
                'job_id': request.job_id,
                'qualified_job_id': payload.get('qualified_job_id', scope.qualify_job_id(request.job_id)),
            })
        raw_scope = payload.get('tenant_queue_scope') if isinstance(payload.get('tenant_queue_scope'), Mapping) else None
        if raw_scope is not None:
            declared_tenant = str(raw_scope.get('tenant_id') or '').strip()
            declared_queue = str(raw_scope.get('queue_name') or '').strip()
            declared_namespace = str(raw_scope.get('namespace') or scope.namespace).strip() or scope.namespace
            if require_tenant_id(declared_tenant) != scope.tenant_id:
                raise ValueError('tenant_queue_scope tenant mismatch')
            if declared_queue != scope.queue_name:
                raise ValueError('tenant_queue_scope queue mismatch')
            if declared_namespace != scope.namespace:
                raise ValueError('tenant_queue_scope namespace mismatch')
            declared_scope_key = str(raw_scope.get('scope_key') or '').strip()
            if declared_scope_key and declared_scope_key != scope.scope_key:
                raise ValueError('tenant_queue_scope scope_key mismatch')
        qualified_job_id = payload.get('qualified_job_id')
        if qualified_job_id is not None:
            scope.assert_belongs_to_scope(str(qualified_job_id))
        qualified_dedupe_key = payload.get('qualified_dedupe_key')
        if qualified_dedupe_key is not None:
            scope.assert_belongs_to_scope(str(qualified_dedupe_key))

    @staticmethod
    def _resolution_value(decision: Any) -> str | None:
        resolution = getattr(decision, 'resolution', None)
        return None if resolution is None else str(resolution.value)

    @staticmethod
    def _rate_limited(verdict: RateLimitVerdict, *, idempotency_decision: Any = None) -> DispatchVerdict:
        return DispatchVerdict(False, None, verdict.reason, int(verdict.retry_after_seconds), JobDispatcher._resolution_value(idempotency_decision))


__all__ = [
    'CANON_RUNTIME_QUEUE_DISPATCHER',
    'DispatchVerdict',
    'JobDispatcher',
]
