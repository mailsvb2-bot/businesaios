from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from application.business_autonomy.provider_admin_contract import ProviderActivationStatus
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import PROVIDER_CREATED, PROVIDER_UPDATED
from core.tenancy.normalization import require_tenant_id
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore

CANON_PROVIDER_ACTIVATION_STORE = True
CANON_PROVIDER_EVENT_SPINE_PROJECTION = True
_PROVIDER_EVENT_NAMESPACE = UUID("7ca7175a-e7f8-4f56-87ce-852311519718")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _epoch_ms(value: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("invalid provider activation timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0, int(parsed.timestamp() * 1000))


class _ProviderActivationEventSpineProjection:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    @staticmethod
    def _event_type(version: int) -> str:
        return PROVIDER_CREATED if int(version) == 1 else PROVIDER_UPDATED

    @classmethod
    def _event_id(
        cls,
        *,
        status: ProviderActivationStatus,
        version: int,
    ) -> str:
        semantic = ":".join(
            (
                status.tenant_id,
                status.business_id,
                status.provider_key,
                str(int(version)),
            )
        )
        return str(uuid5(_PROVIDER_EVENT_NAMESPACE, semantic))

    def project(self, *, status: ProviderActivationStatus, version: int) -> str:
        event_type = self._event_type(version)
        event_id = self._event_id(status=status, version=version)
        occurred_at_ms = _epoch_ms(status.last_updated_utc)
        event = {
            "event_id": event_id,
            "tenant_id": status.tenant_id,
            "source": "runtime.business_autonomy.provider_activation_store",
            "event_type": event_type,
            "timestamp_ms": occurred_at_ms,
            "decision_id": None,
            "correlation_id": None,
            "payload": {
                "schema_version": 1,
                "business_id": status.business_id,
                "occurred_at_ms": occurred_at_ms,
                "recorded_at_ms": occurred_at_ms,
                "provider_key": status.provider_key,
                "provider_version": int(version),
                "connected": bool(status.connected),
                "connector_id": status.connector_id,
                "channel_kind": status.channel_kind,
                "governance_enabled": bool(status.governance_enabled),
                "onboarding_ready": bool(status.onboarding_ready),
                "persistent_surfaces": list(status.persistent_surfaces),
            },
        }
        matches = [
            dict(raw)
            for raw in self._events.iter_events(
                tenant_id=status.tenant_id,
                start_ms=0,
                event_type=event_type,
            )
            if str(raw.get("event_id") or "") == event_id
        ]
        if len(matches) > 1:
            raise RuntimeError("PROVIDER_EVENT_SPINE_DUPLICATE")
        if matches:
            if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
                raise RuntimeError("PROVIDER_EVENT_SPINE_CONFLICT")
            return event_id
        try:
            self._events.append_event(event)
        except Exception:
            matches = [
                dict(raw)
                for raw in self._events.iter_events(
                    tenant_id=status.tenant_id,
                    start_ms=0,
                    event_type=event_type,
                )
                if str(raw.get("event_id") or "") == event_id
            ]
            if (
                len(matches) != 1
                or canonical_business_event_contract(matches[0])
                != canonical_business_event_contract(event)
            ):
                raise
            return event_id
        matches = [
            dict(raw)
            for raw in self._events.iter_events(
                tenant_id=status.tenant_id,
                start_ms=0,
                event_type=event_type,
            )
            if str(raw.get("event_id") or "") == event_id
        ]
        if len(matches) != 1:
            raise RuntimeError("PROVIDER_EVENT_SPINE_APPEND_NOT_DURABLE")
        if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise RuntimeError("PROVIDER_EVENT_SPINE_CONFLICT")
        return event_id


@dataclass(frozen=True)
class FileProviderActivationStore:
    documents: FileDistributedDocumentStore
    collection: str = "provider_activation_state"
    event_store: Any | None = None
    require_event_spine: bool = False

    def __post_init__(self) -> None:
        if self.require_event_spine and self.event_store is None:
            raise RuntimeError("PROVIDER_EVENT_STORE_REQUIRED")

    @staticmethod
    def _status_payload(status: ProviderActivationStatus) -> dict[str, Any]:
        return {
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
        }

    @staticmethod
    def _semantic_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row.pop("version", None)
        row.pop("updated_at_utc", None)
        row.pop("last_updated_utc", None)
        return row

    def _project_payload(self, payload: Mapping[str, Any]) -> None:
        if self.event_store is None:
            return
        version = int(payload.get("version") or 0)
        if version <= 0:
            raise RuntimeError("PROVIDER_DOCUMENT_VERSION_REQUIRED")
        _ProviderActivationEventSpineProjection(self.event_store).project(
            status=self._from_payload(payload),
            version=version,
        )

    def put(self, status: ProviderActivationStatus) -> ProviderActivationStatus:
        status.validate_scope()
        doc_id = self._doc_id(status.tenant_id, status.business_id, status.provider_key)
        current = self.documents.get(collection=self.collection, document_id=doc_id)
        candidate = self._status_payload(status)
        if current is not None:
            current_status = self._from_payload(current)
            if self._doc_id(current_status.tenant_id, current_status.business_id, current_status.provider_key) != doc_id:
                raise RuntimeError("PROVIDER_ACTIVATION_SCOPE_MISMATCH")
            self._project_payload(current)
            if self._semantic_payload(current) == self._semantic_payload(candidate):
                return current_status
        expected_version = None if current is None else int(current.get("version") or 0)
        self.documents.put(
            collection=self.collection,
            document_id=doc_id,
            payload=candidate,
            expected_version=expected_version,
        )
        saved_payload = self.documents.get(collection=self.collection, document_id=doc_id)
        if saved_payload is None:
            raise RuntimeError("PROVIDER_ACTIVATION_WRITE_NOT_DURABLE")
        self._project_payload(saved_payload)
        return self._from_payload(saved_payload)

    def get(self, *, tenant_id: str, business_id: str, provider_key: str) -> ProviderActivationStatus | None:
        doc_id = self._doc_id(tenant_id, business_id, provider_key)
        payload = self.documents.get(collection=self.collection, document_id=doc_id)
        if payload is None:
            return None
        status = self._from_payload(payload)
        if self._doc_id(status.tenant_id, status.business_id, status.provider_key) != doc_id:
            raise RuntimeError("PROVIDER_ACTIVATION_SCOPE_MISMATCH")
        return status

    def list_for_business(self, *, tenant_id: str, business_id: str, limit: int = 100) -> tuple[ProviderActivationStatus, ...]:
        tenant = require_tenant_id(tenant_id)
        business = str(business_id or "").strip()
        if not business:
            raise ValueError("business_id is required")
        rows = self.documents.list_prefix(
            collection=self.collection,
            prefix=f"{tenant}:{business}:",
            limit=max(1, int(limit)),
        )
        statuses = []
        for row in rows:
            status = self._from_payload(row)
            if status.tenant_id != tenant or status.business_id != business:
                raise RuntimeError("PROVIDER_ACTIVATION_SCOPE_MISMATCH")
            statuses.append(status)
        return tuple(statuses)

    @staticmethod
    def _doc_id(tenant_id: str, business_id: str, provider_key: str) -> str:
        tenant = require_tenant_id(tenant_id)
        business = str(business_id or "").strip()
        provider = str(provider_key or "").strip()
        if not business:
            raise ValueError("business_id is required")
        if not provider:
            raise ValueError("provider_key is required")
        return f"{tenant}:{business}:{provider}"

    @staticmethod
    def _from_payload(payload: Mapping[str, Any]) -> ProviderActivationStatus:
        status = ProviderActivationStatus(
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
        status.validate_scope()
        return status


__all__ = ["CANON_PROVIDER_ACTIVATION_STORE", "CANON_PROVIDER_EVENT_SPINE_PROJECTION", "FileProviderActivationStore"]
