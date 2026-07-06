from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.tenancy.normalization import require_tenant_id
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore

CANON_PLATFORM_ADMIN_LAYOUT_STORE = True


@dataclass(frozen=True)
class FilePlatformAdminLayoutStore:
    documents: FileDistributedDocumentStore
    collection: str = 'platform_admin_layouts'

    def read_layout(self, *, tenant_id: str) -> dict[str, Any] | None:
        item = self.documents.get(collection=self.collection, document_id=require_tenant_id(tenant_id))
        return None if item is None else dict(item)

    def write_layout(self, *, tenant_id: str, layout: Mapping[str, Any]) -> dict[str, Any]:
        key = require_tenant_id(tenant_id)
        current = self.documents.get(collection=self.collection, document_id=key)
        expected_version = None if current is None else int(current.get('version') or 0)
        self.documents.put(collection=self.collection, document_id=key, payload={'tenant_id': key, 'layout': dict(layout or {})}, expected_version=expected_version)
        return self.read_layout(tenant_id=key) or {'tenant_id': key, 'layout': dict(layout or {})}
