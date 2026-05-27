from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from application.business_autonomy.provider_admin_contract import ProviderActivationStatus
from core.tenancy.normalization import require_tenant_id
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore

CANON_PROVIDER_ACTIVATION_STORE = True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FileProviderActivationStore:
    documents: FileDistributedDocumentStore
    collection: str = "provider_activation_state"

    def put(self, status: ProviderActivationStatus) -> ProviderActivationStatus:
        doc_id = self._doc_id(status.tenant_id, status.business_id, status.provider_key)
        current = self.documents.get(collection=self.collection, document_id=doc_id)
        expected_version = None if current is None else int(current.get("version") or 0)
        self.documents.put(
            collection=self.collection,
            document_id=doc_id,
            payload={
                "tenant_id": status.tenant_id,
                "business_id": status.business_id,
                "provider_key": status.provider_key,
                "connected": bool(status.connected),
                "connector_id": status.connector_id,
                "title": status.title,
                "channel_kind": status.channel_kind,
                "secret_fields_bound": list(status.secret_fields_bound),
                "last_updated_utc": status.last_updated_utc or _now(),
                "governance_enabled": bool(status.governance_enabled),
                "persistent_surfaces": list(status.persistent_surfaces),
                "onboarding_ready": bool(status.onboarding_ready),
                "metadata": dict(status.metadata or {}),
            },
            expected_version=expected_version,
        )
        return self.get(tenant_id=status.tenant_id, business_id=status.business_id, provider_key=status.provider_key)

    def get(self, *, tenant_id: str, business_id: str, provider_key: str) -> ProviderActivationStatus | None:
        payload = self.documents.get(collection=self.collection, document_id=self._doc_id(tenant_id, business_id, provider_key))
        return None if payload is None else self._from_payload(payload)

    def list_for_business(self, *, tenant_id: str, business_id: str, limit: int = 100) -> tuple[ProviderActivationStatus, ...]:
        rows = self.documents.list_prefix(
            collection=self.collection,
            prefix=f"{require_tenant_id(tenant_id)}:{str(business_id).strip()}:",
            limit=max(1, int(limit)),
        )
        return tuple(self._from_payload(row) for row in rows)

    @staticmethod
    def _doc_id(tenant_id: str, business_id: str, provider_key: str) -> str:
        return f"{require_tenant_id(tenant_id)}:{str(business_id).strip()}:{str(provider_key).strip()}"

    @staticmethod
    def _from_payload(payload: Mapping[str, Any]) -> ProviderActivationStatus:
        return ProviderActivationStatus(
            tenant_id=require_tenant_id(payload.get("tenant_id")),
            business_id=str(payload.get("business_id") or "").strip(),
            provider_key=str(payload.get("provider_key") or "").strip(),
            connected=bool(payload.get("connected")),
            connector_id=str(payload.get("connector_id") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            channel_kind=str(payload.get("channel_kind") or "").strip(),
            secret_fields_bound=tuple(sorted(str(item) for item in list(payload.get("secret_fields_bound") or []) if str(item).strip())),
            last_updated_utc=str(payload.get("last_updated_utc") or "").strip(),
            governance_enabled=bool(payload.get("governance_enabled")),
            persistent_surfaces=tuple(sorted(str(item) for item in list(payload.get("persistent_surfaces") or []) if str(item).strip())),
            onboarding_ready=bool(payload.get("onboarding_ready")),
            metadata=dict(payload.get("metadata") or {}),
        )


__all__ = ["CANON_PROVIDER_ACTIVATION_STORE", "FileProviderActivationStore"]
