from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore

CANON_PROVIDER_SYNC_HISTORY = True


def _runtime_root() -> Path:
    from application.business_autonomy.persistence import business_autonomy_runtime_dir
    return business_autonomy_runtime_dir() / 'distributed' / 'provider_sync_history'


class ProviderSyncHistoryStore(Protocol):
    def append(self, row: Mapping[str, Any]) -> dict[str, Any]: ...
    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]: ...
    def find_for_queue_jobs(self, *, tenant_id: str, business_id: str, provider_key: str, queue_job_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]: ...


@dataclass
class InMemoryProviderSyncHistoryStore:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def append(self, row: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(row)
        self.rows.append(item)
        return item

    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows = [dict(item) for item in self.rows if str(item.get('tenant_id')) == str(tenant_id) and str(item.get('business_id')) == str(business_id) and str(item.get('provider_key')) == str(provider_key)]
        rows.sort(key=lambda row: str(row.get('recorded_at_utc') or ''), reverse=True)
        return tuple(rows[:max(1, int(limit))])
    def find_for_queue_jobs(self, *, tenant_id: str, business_id: str, provider_key: str, queue_job_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        wanted = {str(job_id) for job_id in queue_job_ids}
        return {str(item.get('queue_job_id')): dict(item) for item in self.rows if str(item.get('queue_job_id')) in wanted and str(item.get('tenant_id')) == str(tenant_id) and str(item.get('business_id')) == str(business_id) and str(item.get('provider_key')) == str(provider_key)}
@dataclass(frozen=True)
class FileProviderSyncHistoryStore:
    documents: FileDistributedDocumentStore
    collection: str = 'provider_sync_history'

    @classmethod
    def default(cls) -> FileProviderSyncHistoryStore:
        return cls(FileDistributedDocumentStore(_runtime_root() / 'documents'))

    def append(self, row: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        history_id = str(payload.get('history_id') or uuid4())
        payload['history_id'] = history_id
        self.documents.put(collection=self.collection, document_id=history_id, payload=payload)
        return dict(self.documents.get(collection=self.collection, document_id=history_id) or payload)

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
        result.sort(key=lambda row: str(row.get('recorded_at_utc') or ''), reverse=True)
        return tuple(result)
    def find_for_queue_jobs(self, *, tenant_id: str, business_id: str, provider_key: str, queue_job_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        return {job_id: dict(row) for job_id, row in self.documents.find_exact_many(collection=self.collection, fields={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key}, key_field='queue_job_id', keys=queue_job_ids).items()}

@dataclass(frozen=True)
class ProviderSyncHistory:
    store: ProviderSyncHistoryStore = field(default_factory=FileProviderSyncHistoryStore.default)

    def append(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return self.store.append(row)

    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        return self.store.list_for_provider(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)
    def find_for_queue_jobs(self, *, tenant_id: str, business_id: str, provider_key: str, queue_job_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        return self.store.find_for_queue_jobs(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, queue_job_ids=queue_job_ids)


__all__ = ['CANON_PROVIDER_SYNC_HISTORY', 'ProviderSyncHistory', 'InMemoryProviderSyncHistoryStore', 'FileProviderSyncHistoryStore']
