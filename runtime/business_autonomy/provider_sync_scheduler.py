from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Mapping
from uuid import uuid4

from application.business_autonomy.provider_runtime_contract import ProviderScheduledSyncResult
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_retry_policy import ProviderRetryPolicy

CANON_PROVIDER_SYNC_SCHEDULER = True


def _runtime_root() -> Path:
    from application.business_autonomy.persistence import business_autonomy_runtime_dir
    return business_autonomy_runtime_dir() / 'distributed' / 'provider_scheduler'


class ProviderSyncScheduleStore(Protocol):
    def append(self, job: Mapping[str, Any]) -> dict[str, Any]: ...
    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]: ...


@dataclass
class InMemoryProviderSyncScheduleStore:
    jobs: list[dict[str, Any]] = field(default_factory=list)

    def append(self, job: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(job)
        self.jobs.append(row)
        return row

    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows = [dict(item) for item in self.jobs if str(item.get('tenant_id')) == str(tenant_id) and str(item.get('business_id')) == str(business_id) and str(item.get('provider_key')) == str(provider_key)]
        rows.sort(key=lambda row: str(row.get('run_at') or ''), reverse=True)
        return tuple(rows[: max(1, int(limit))])


@dataclass(frozen=True)
class FileProviderSyncScheduleStore:
    documents: FileDistributedDocumentStore
    collection: str = 'provider_sync_jobs'

    @classmethod
    def default(cls) -> FileProviderSyncScheduleStore:
        return cls(FileDistributedDocumentStore(_runtime_root() / 'documents'))

    def append(self, job: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(job)
        job_id = str(row.get('job_id') or uuid4())
        row['job_id'] = job_id
        self.documents.put(collection=self.collection, document_id=job_id, payload=row)
        return dict(self.documents.get(collection=self.collection, document_id=job_id) or row)

    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows = self.documents.list_prefix(collection=self.collection, prefix='', limit=max(limit * 5, limit))
        result = []
        for item in rows:
            if str(item.get('tenant_id')) != str(tenant_id):
                continue
            if str(item.get('business_id')) != str(business_id):
                continue
            if str(item.get('provider_key')) != str(provider_key):
                continue
            result.append(dict(item))
            if len(result) >= max(1, int(limit)):
                break
        return tuple(result)


@dataclass(frozen=True)
class ProviderSyncScheduler:
    retry_policy: ProviderRetryPolicy = field(default_factory=ProviderRetryPolicy)
    store: ProviderSyncScheduleStore = field(default_factory=FileProviderSyncScheduleStore.default)

    def schedule_retry(self, *, provider_key: str, operation: str, category: str, retryable: bool, tenant_id: str, business_id: str, attempts: int = 1) -> ProviderScheduledSyncResult:
        decision = self.retry_policy.evaluate(provider_key=provider_key, category=category, retryable=retryable)
        if not decision.retryable:
            return ProviderScheduledSyncResult(provider_key=provider_key, operation=operation, scheduled=False, status='retry_rejected', metadata={'category': category, 'attempts': attempts})
        run_at = datetime.now(UTC) + timedelta(seconds=int(decision.next_delay_seconds or 0))
        job = self.store.append({'job_id': str(uuid4()), 'provider_key': provider_key, 'operation': operation, 'tenant_id': tenant_id, 'business_id': business_id, 'attempts': attempts, 'run_at': run_at.isoformat(), 'category': category, 'scheduled_at_utc': datetime.now(UTC).isoformat(), 'status': 'scheduled'})
        return ProviderScheduledSyncResult(provider_key=provider_key, operation=operation, scheduled=True, status='retry_scheduled', metadata={'job': job, 'max_attempts': decision.max_attempts})

    def list_jobs(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        return self.store.list_for_provider(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)


__all__ = ['CANON_PROVIDER_SYNC_SCHEDULER', 'InMemoryProviderSyncScheduleStore', 'FileProviderSyncScheduleStore', 'ProviderSyncScheduler']
