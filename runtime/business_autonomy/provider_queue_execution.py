from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.queue.job_contract import JobDispatchRequest, JobResult
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

    def enqueue_sync(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, mode: str = 'live', payload: Mapping[str, Any] | None = None, queue_name: str = _PROVIDER_QUEUE_NAME) -> ProviderQueueDispatchResult:
        normalized_payload = {
            'provider_key': provider.provider_key,
            'business_id': str(business_id),
            'operation': str(operation),
            'mode': str(mode or 'live'),
            'payload': dict(payload or {}),
        }
        job_id = f"provider-sync-{provider.provider_key}-{uuid4().hex}"
        req = JobDispatchRequest(
            tenant_id=str(tenant_id),
            job_id=job_id,
            queue_name=str(queue_name),
            job_type=_PROVIDER_JOB_TYPE,
            payload=normalized_payload,
            dedupe_key=f"{provider.provider_key}:{business_id}:{operation}:{normalized_payload['mode']}:{uuid4().hex[:8]}",
            tags=(f"provider:{provider.provider_key}", f"business:{business_id}"),
        )
        self.store.put(req.to_record())
        return ProviderQueueDispatchResult(job_id=job_id, queued=True, status='queued', metadata={'queue_name': str(queue_name), 'job_type': _PROVIDER_JOB_TYPE, 'provider_key': provider.provider_key})

    def tick(self, *, provider_registry: Mapping[str, ProviderDefinition], tenant_id: str, queue_name: str = _PROVIDER_QUEUE_NAME, worker_id: str = 'provider-runtime-worker') -> Mapping[str, Any]:
        scheduler = JobScheduler(store=self.store)
        worker = JobWorker(worker_id=str(worker_id).strip() or 'provider-runtime-worker', store=self.store, scheduler=scheduler, runner=self._runner(provider_registry))
        report = worker.tick(tenant_id=str(tenant_id), queue_name=str(queue_name))
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
        return {
            'tenant_id': tid,
            'queue_name': str(queue_name),
            'pending': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.PENDING),
            'claimed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.CLAIMED),
            'completed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.SUCCEEDED),
            'failed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.FAILED),
        }

    def _runner(self, provider_registry: Mapping[str, ProviderDefinition]):
        runtime = self.live_runtime
        def _run(job) -> JobResult:
            payload = dict(job.payload or {})
            provider_key = str(payload.get('provider_key') or '').strip()
            provider = provider_registry[provider_key]
            result: ProviderSyncRunResult = runtime.run(provider=provider, tenant_id=job.tenant_id, business_id=str(payload.get('business_id') or ''), operation=str(payload.get('operation') or ''), mode=str(payload.get('mode') or 'live'), payload=dict(payload.get('payload') or {}))
            ok = bool(result.accepted)
            return JobResult(ok=ok, status=result.status, job_id=job.job_id, tenant_id=job.tenant_id, attempts=job.attempts, output={'provider_key': result.provider_key, 'operation': result.operation, 'mode': result.mode, 'metadata': dict(result.metadata or {})}, error=None if ok else result.status)
        return _run


__all__ = ['CANON_PROVIDER_QUEUE_EXECUTION', 'ProviderQueueDispatchResult', 'ProviderQueueExecutionRuntime']
