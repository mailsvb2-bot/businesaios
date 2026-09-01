from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_runtime_write_guard import ProviderRuntimeWriteGuard
from runtime.queue.job_contract import JobDispatchRequest, JobResult
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_worker import JobWorker
from security.secret_vault import SecretVault

CANON_PROVIDER_QUEUE_EXECUTION = True
_PROVIDER_QUEUE_NAME = 'provider_sync'
_PROVIDER_JOB_TYPE = 'provider_sync.dispatch'


def _queue_store_path() -> Path:
    from application.business_autonomy.persistence import business_autonomy_runtime_dir
    return business_autonomy_runtime_dir() / 'queue' / 'provider_sync_jobs.sqlite3'


@dataclass(frozen=True)
class ProviderQueueDispatchResult:
    job_id: str
    queued: bool
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderQueueExecutionRuntime:
    secret_vault: SecretVault
    live_runtime: ProviderLiveSyncRuntime
    store: SqliteJobStore = field(default_factory=lambda: SqliteJobStore(_queue_store_path()))
    write_guard: ProviderRuntimeWriteGuard = field(default_factory=ProviderRuntimeWriteGuard)
    idempotency_store: Any | None = None

    def enqueue_sync(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, mode: str = 'live', payload: Mapping[str, Any] | None = None, queue_name: str = _PROVIDER_QUEUE_NAME) -> ProviderQueueDispatchResult:
        normalized_mode = str(mode or 'live').strip().lower() or 'live'
        normalized_operation = str(operation).strip()
        guard_decision = self.write_guard.evaluate(provider=provider, operation=normalized_operation, mode=normalized_mode, tenant_id=str(tenant_id), business_id=str(business_id), payload=dict(payload or {}))
        if not guard_decision.allowed:
            return ProviderQueueDispatchResult(
                job_id='', queued=False, status=guard_decision.status,
                metadata={'queue_name': str(queue_name), 'job_type': _PROVIDER_JOB_TYPE, 'provider_key': provider.provider_key, 'provider_write_guard': guard_decision.to_metadata(), 'fail_closed_before_queue': True},
            )
        truth = provider_truth_map().get(provider.provider_key)
        guarded_message_send = normalized_mode == 'live' and normalized_operation == 'message_send' and bool(truth and truth.write_supported and truth.approval_required)
        approval_fingerprint = str(dict(guard_decision.metadata.get('approval') or {}).get('subject_fingerprint') or '').strip()
        execution_identity = approval_fingerprint if guarded_message_send and approval_fingerprint else uuid4().hex
        normalized_payload = {'provider_key': provider.provider_key, 'business_id': str(business_id), 'operation': normalized_operation, 'mode': normalized_mode, 'payload': dict(payload or {})}
        job_id = f"provider-sync-{provider.provider_key}-{execution_identity[:32]}"
        req = JobDispatchRequest(
            tenant_id=str(tenant_id), job_id=job_id, queue_name=str(queue_name), job_type=_PROVIDER_JOB_TYPE, payload=normalized_payload,
            dedupe_key=f"{provider.provider_key}-{normalized_operation}-{execution_identity}",
            max_attempts=1 if guarded_message_send else (6 if provider.provider_key in {'vk_messaging', 'max_messaging'} else 8),
            tags=(f"provider:{provider.provider_key}", f"business:{business_id}"),
        )
        dispatch = JobDispatcher(store=self.store, idempotency_store=self.idempotency_store).dispatch(req)
        return ProviderQueueDispatchResult(job_id='' if dispatch.job is None else dispatch.job.job_id, queued=dispatch.accepted, status='queued' if dispatch.reason == 'accepted' else dispatch.reason, metadata={'queue_name': str(queue_name), 'job_type': _PROVIDER_JOB_TYPE, 'provider_key': provider.provider_key, 'provider_write_guard': guard_decision.to_metadata(), 'idempotency_resolution': dispatch.idempotency_resolution})

    def tick(self, *, provider_registry: Mapping[str, ProviderDefinition], tenant_id: str, queue_name: str = _PROVIDER_QUEUE_NAME, worker_id: str = 'provider-runtime-worker', job_id: str | None = None) -> Mapping[str, Any]:
        scheduler = JobScheduler(store=self.store)
        worker = JobWorker(worker_id=str(worker_id).strip() or 'provider-runtime-worker', store=self.store, scheduler=scheduler, runner=self._runner(provider_registry))
        report = worker.tick(tenant_id=str(tenant_id), queue_name=str(queue_name), job_id=job_id)
        return {**dict(report.__dict__), 'worker_id': str(worker_id).strip() or 'provider-runtime-worker'}

    def list_jobs(self, *, tenant_id: str, business_id: str | None = None, provider_key: str, queue_name: str = _PROVIDER_QUEUE_NAME, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows = self.store.list_due(tenant_id=str(tenant_id), queue_name=str(queue_name), limit=int(limit))
        out = []
        for row in rows:
            if str(row.payload.get('provider_key')) != str(provider_key):
                continue
            if business_id is not None and str(row.payload.get('business_id')) != str(business_id):
                continue
            out.append({'job_id': row.job_id, 'job_type': row.job_type, 'queue_name': row.queue_name, 'state': row.state.value, 'attempts': row.attempts, 'run_at': row.run_at.isoformat(), 'payload': dict(row.payload)})
        return tuple(out)

    def metrics(self, *, tenant_id: str, queue_name: str = _PROVIDER_QUEUE_NAME) -> Mapping[str, Any]:
        from runtime.queue.job_contract import JobState
        tid = str(tenant_id)
        return {'tenant_id': tid, 'queue_name': str(queue_name), 'pending': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.PENDING), 'claimed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.CLAIMED), 'completed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.SUCCEEDED), 'failed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.FAILED)}

    def _runner(self, provider_registry: Mapping[str, ProviderDefinition]):
        runtime = self.live_runtime
        def _run(job) -> JobResult:
            payload = dict(job.payload or {})
            provider_key = str(payload.get('provider_key') or '').strip()
            provider = provider_registry[provider_key]
            result: ProviderSyncRunResult = runtime.run(provider=provider, tenant_id=job.tenant_id, business_id=str(payload.get('business_id') or ''), operation=str(payload.get('operation') or ''), mode=str(payload.get('mode') or 'live'), payload=dict(payload.get('payload') or {}), attempts=max(1, int(job.attempts)), _queue_job_id=job.job_id)
            ok, retry = bool(result.accepted), dict(result.metadata.get('retry_policy') or {})
            retryable, category = bool(retry.get('retryable')), str(retry.get('category') or 'provider_runtime_error')
            return JobResult(ok=ok, status=result.status, job_id=job.job_id, tenant_id=job.tenant_id, attempts=job.attempts, output={'provider_key': result.provider_key, 'operation': result.operation, 'mode': result.mode, 'metadata': dict(result.metadata or {})}, error=None if ok else (category.upper() if retryable else f'NON_RETRYABLE:{category}'), retry_delay_seconds=int(retry.get('next_delay_seconds') or 0) if retryable else None)
        return _run


__all__ = ['CANON_PROVIDER_QUEUE_EXECUTION', 'ProviderQueueDispatchResult', 'ProviderQueueExecutionRuntime']
