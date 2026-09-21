from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid5

from application.business_autonomy.channel_contracts import ChannelIdentity, ChannelKind
from application.business_autonomy.contracts import BusinessCapability, CapabilityKind
from application.business_autonomy.registry import RegisteredBusinessCapabilities
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier
from contracts.business_profile import BusinessProfile
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import BUSINESS_CREATED, BUSINESS_UPDATED
from core.tenancy.normalization import require_tenant_id

CANON_DISTRIBUTED_BUSINESS_REGISTRY = True
CANON_BUSINESS_LIFECYCLE_OWNER = True
CANON_BUSINESS_LIFECYCLE_EVENT_SPINE_PROJECTION = True
_BUSINESS_EVENT_NAMESPACE = UUID("2f6e88e6-6d8a-4690-9b8c-b9f28fe2b7ab")


class DistributedDocumentPort(Protocol):
    def get(self, *, collection: str, document_id: str) -> Mapping[str, Any] | None: ...
    def put(self, *, collection: str, document_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int: ...
    def list_prefix(self, *, collection: str, prefix: str, limit: int = 100) -> Sequence[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class BusinessRegistryRecord:
    business_id: str
    tenant_id: str
    ownership_key: str
    region: str
    channel_kind: str
    capabilities: tuple[BusinessCapability, ...]
    trust: BusinessTrustSnapshot
    governance_enabled: bool
    persistent_surfaces: tuple[str, ...]
    channel_adapter_key: str = ""
    channel_external_ref: str = ""
    version: int = 0
    updated_at_utc: str = ""

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.business_id or "").strip():
            raise ValueError("business_id is required")
        if not str(self.ownership_key or "").strip():
            raise ValueError("ownership_key is required")
        if not str(self.region or "").strip():
            raise ValueError("region is required")
        if not str(self.channel_kind or "").strip():
            raise ValueError("channel_kind is required")
        adapter_key = str(self.channel_adapter_key or "").strip()
        external_ref = str(self.channel_external_ref or "").strip()
        if bool(adapter_key) != bool(external_ref):
            raise ValueError("channel_adapter_key and channel_external_ref must be provided together")
        if self.trust.business_id and self.trust.business_id != self.business_id:
            raise ValueError("trust.business_id must match business_id")

    @property
    def document_id(self) -> str:
        return f"{self.tenant_id}:{self.business_id}"

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "business_id": self.business_id,
            "tenant_id": self.tenant_id,
            "ownership_key": self.ownership_key,
            "region": self.region,
            "channel_kind": self.channel_kind,
            "channel_adapter_key": str(self.channel_adapter_key or "").strip(),
            "channel_external_ref": str(self.channel_external_ref or "").strip(),
            "capabilities": [
                {
                    "kind": item.kind.value,
                    "enabled": bool(item.enabled),
                    "confidence": float(item.confidence),
                    "notes": item.notes,
                }
                for item in self.capabilities
            ],
            "trust": {
                "business_id": self.business_id,
                "trust_tier": self.trust.trust_tier.value,
                "score": float(self.trust.score),
                "reasons": list(self.trust.reasons),
                "metadata": dict(self.trust.metadata or {}),
            },
            "governance_enabled": bool(self.governance_enabled),
            "persistent_surfaces": sorted({str(item) for item in self.persistent_surfaces if str(item).strip()}),
            "version": int(self.version),
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> BusinessRegistryRecord:
        trust_raw = dict(payload.get("trust") or {})
        capability_rows = [item for item in list(payload.get("capabilities") or []) if isinstance(item, Mapping)]
        record = cls(
            business_id=str(payload.get("business_id") or "").strip(),
            tenant_id=require_tenant_id(payload.get("tenant_id")),
            ownership_key=str(payload.get("ownership_key") or "").strip(),
            region=str(payload.get("region") or "global").strip() or "global",
            channel_kind=str(payload.get("channel_kind") or "unknown").strip() or "unknown",
            capabilities=tuple(
                BusinessCapability(
                    kind=CapabilityKind(str(item.get("kind") or CapabilityKind.ANALYTICS_ENGINE.value)),
                    enabled=bool(item.get("enabled", True)),
                    confidence=max(0.0, min(1.0, float(item.get("confidence") or 0.0))),
                    notes=None if item.get("notes") in (None, "") else str(item.get("notes")),
                )
                for item in capability_rows
            ),
            trust=BusinessTrustSnapshot(
                business_id=str(trust_raw.get("business_id") or payload.get("business_id") or "").strip(),
                trust_tier=BusinessTrustTier(str(trust_raw.get("trust_tier") or BusinessTrustTier.UNKNOWN.value)),
                score=max(0.0, min(1.0, float(trust_raw.get("score") or 0.0))),
                reasons=tuple(str(item) for item in list(trust_raw.get("reasons") or [])),
                metadata=dict(trust_raw.get("metadata") or {}),
            ),
            governance_enabled=bool(payload.get("governance_enabled", False)),
            persistent_surfaces=tuple(sorted({str(item) for item in list(payload.get("persistent_surfaces") or []) if str(item).strip()})),
            channel_adapter_key=str(payload.get("channel_adapter_key") or "").strip(),
            channel_external_ref=str(payload.get("channel_external_ref") or "").strip(),
            version=max(0, int(payload.get("version") or 0)),
            updated_at_utc=str(payload.get("updated_at_utc") or ""),
        )
        record.validate()
        return record


class _BusinessRegistryEventSpineProjection:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    @staticmethod
    def _event_id(record: BusinessRegistryRecord) -> str:
        return str(
            uuid5(
                _BUSINESS_EVENT_NAMESPACE,
                f"{record.tenant_id}:{record.business_id}:{int(record.version)}",
            )
        )

    @staticmethod
    def _timestamp_ms(record: BusinessRegistryRecord) -> int | None:
        raw = str(record.updated_at_utc or "").strip()
        if not raw:
            return None
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)

    def _matches(
        self,
        *,
        tenant_id: str,
        event_type: str,
        event_id: str,
    ) -> list[dict[str, Any]]:
        return [
            dict(raw)
            for raw in self._events.iter_events(
                tenant_id=str(tenant_id),
                start_ms=0,
                event_type=str(event_type),
            )
            if str(raw.get("event_id") or "") == str(event_id)
        ]

    def project(self, record: BusinessRegistryRecord) -> str | None:
        if int(record.version) <= 0:
            raise ValueError("business registry version must be positive before Event Spine projection")
        timestamp_ms = self._timestamp_ms(record)
        if timestamp_ms is None:
            return None
        event_type = BUSINESS_CREATED if int(record.version) == 1 else BUSINESS_UPDATED
        event_id = self._event_id(record)
        event = {
            "event_id": event_id,
            "tenant_id": record.tenant_id,
            "source": "application.business_autonomy.distributed_business_registry",
            "event_type": event_type,
            "timestamp_ms": timestamp_ms,
            "decision_id": None,
            "correlation_id": None,
            "payload": {
                "schema_version": 1,
                "business_id": record.business_id,
                "occurred_at_ms": timestamp_ms,
                "recorded_at_ms": timestamp_ms,
                "registry_version": int(record.version),
                "region": record.region,
                "channel_kind": record.channel_kind,
                "capabilities": [
                    {
                        "kind": item.kind.value,
                        "enabled": bool(item.enabled),
                        "confidence": float(item.confidence),
                    }
                    for item in record.capabilities
                ],
                "trust": {
                    "trust_tier": record.trust.trust_tier.value,
                    "score": float(record.trust.score),
                },
                "governance_enabled": bool(record.governance_enabled),
                "persistent_surfaces": list(record.persistent_surfaces),
                "channel_identity_bound": bool(
                    record.channel_adapter_key and record.channel_external_ref
                ),
            },
        }
        matches = self._matches(
            tenant_id=record.tenant_id,
            event_type=event_type,
            event_id=event_id,
        )
        if len(matches) > 1:
            raise RuntimeError("BUSINESS_EVENT_SPINE_DUPLICATE")
        if matches:
            if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
                raise RuntimeError("BUSINESS_EVENT_SPINE_CONFLICT")
            return event_id
        try:
            self._events.append_event(event)
        except Exception:
            matches = self._matches(
                tenant_id=record.tenant_id,
                event_type=event_type,
                event_id=event_id,
            )
            if (
                len(matches) != 1
                or canonical_business_event_contract(matches[0])
                != canonical_business_event_contract(event)
            ):
                raise
            return event_id
        matches = self._matches(
            tenant_id=record.tenant_id,
            event_type=event_type,
            event_id=event_id,
        )
        if len(matches) != 1:
            raise RuntimeError("BUSINESS_EVENT_SPINE_APPEND_NOT_DURABLE")
        if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise RuntimeError("BUSINESS_EVENT_SPINE_CONFLICT")
        return event_id


class DistributedBusinessRegistry:
    def __init__(
        self,
        *,
        documents: DistributedDocumentPort,
        collection: str = "business_registry",
        event_store: Any | None = None,
        require_event_spine: bool = False,
    ) -> None:
        self._documents = documents
        self._collection = str(collection).strip() or "business_registry"
        if require_event_spine and event_store is None:
            raise RuntimeError("BUSINESS_EVENT_STORE_REQUIRED")
        self._event_spine = (
            None if event_store is None else _BusinessRegistryEventSpineProjection(event_store)
        )

    @staticmethod
    def _semantic_payload(record: BusinessRegistryRecord) -> dict[str, Any]:
        payload = record.to_dict()
        payload.pop("version", None)
        payload.pop("updated_at_utc", None)
        return payload

    def register_or_update(self, record: BusinessRegistryRecord) -> BusinessRegistryRecord:
        record.validate()
        existing_payload = self._documents.get(collection=self._collection, document_id=record.document_id)
        existing_version = 0 if existing_payload is None else int(existing_payload.get("version") or 0)
        existing: BusinessRegistryRecord | None = None
        if existing_payload is not None:
            existing = BusinessRegistryRecord.from_dict(existing_payload)
            if existing.tenant_id != record.tenant_id:
                raise ValueError("business registry tenant reassignment is forbidden")
            if existing.ownership_key != record.ownership_key:
                raise ValueError("business registry ownership_key reassignment is forbidden")
            if (
                existing.channel_adapter_key
                and not record.channel_adapter_key
                and record.channel_kind != existing.channel_kind
            ):
                raise ValueError("channel_kind reassignment requires explicit channel identity")
            if self._event_spine is not None:
                self._event_spine.project(existing)
        adapter_key = str(record.channel_adapter_key or "").strip()
        external_ref = str(record.channel_external_ref or "").strip()
        if existing is not None and not adapter_key and not external_ref:
            adapter_key = existing.channel_adapter_key
            external_ref = existing.channel_external_ref
        candidate = BusinessRegistryRecord(
            business_id=record.business_id,
            tenant_id=record.tenant_id,
            ownership_key=record.ownership_key,
            region=record.region,
            channel_kind=record.channel_kind,
            capabilities=tuple(record.capabilities),
            trust=record.trust,
            governance_enabled=bool(record.governance_enabled),
            persistent_surfaces=tuple(sorted({str(item) for item in record.persistent_surfaces if str(item).strip()})),
            channel_adapter_key=adapter_key,
            channel_external_ref=external_ref,
            version=existing_version,
            updated_at_utc="" if existing is None else existing.updated_at_utc,
        )
        if existing is not None and self._semantic_payload(existing) == self._semantic_payload(candidate):
            return existing
        stamped = BusinessRegistryRecord.from_dict(
            {
                **candidate.to_dict(),
                "version": existing_version + 1,
                "updated_at_utc": datetime.now(UTC).isoformat(),
            }
        )
        persisted_version = self._documents.put(
            collection=self._collection,
            document_id=stamped.document_id,
            payload=stamped.to_dict(),
            expected_version=None if existing_payload is None else existing_version,
        )
        persisted = BusinessRegistryRecord.from_dict(
            {**stamped.to_dict(), "version": persisted_version}
        )
        if self._event_spine is not None:
            self._event_spine.project(persisted)
        return persisted

    def get(self, tenant_id: str, business_id: str) -> BusinessRegistryRecord | None:
        payload = self._documents.get(
            collection=self._collection,
            document_id=f"{require_tenant_id(tenant_id)}:{str(business_id).strip()}",
        )
        return None if payload is None else BusinessRegistryRecord.from_dict(payload)

    def list_for_tenant(self, *, tenant_id: str, limit: int = 100) -> tuple[BusinessRegistryRecord, ...]:
        normalized_tenant = require_tenant_id(tenant_id)
        rows = self._documents.list_prefix(
            collection=self._collection,
            prefix=f"{normalized_tenant}:",
            limit=max(1, int(limit)),
        )
        items = [BusinessRegistryRecord.from_dict(item) for item in rows]
        items.sort(key=lambda item: (item.updated_at_utc, item.business_id), reverse=True)
        return tuple(items)

    def list_all(self, *, limit: int = 1000) -> tuple[BusinessRegistryRecord, ...]:
        rows = self._documents.list_prefix(
            collection=self._collection,
            prefix="",
            limit=max(1, int(limit)),
        )
        items = [BusinessRegistryRecord.from_dict(item) for item in rows]
        items.sort(key=lambda item: (item.updated_at_utc, item.tenant_id, item.business_id), reverse=True)
        return tuple(items)

    def find_unique_by_business_id(self, business_id: str, *, limit: int = 1000) -> BusinessRegistryRecord | None:
        key = str(business_id).strip()
        if not key:
            raise ValueError("business_id is required")
        matches = [item for item in self.list_all(limit=limit) if item.business_id == key]
        if not matches:
            return None
        tenants = {item.tenant_id for item in matches}
        if len(tenants) > 1:
            raise KeyError(f"business registry tenant binding ambiguous: {key}")
        return matches[0]

    def profile_snapshot(self, *, tenant_id: str, business_id: str) -> BusinessProfile:
        record = self.get(tenant_id=tenant_id, business_id=business_id)
        if record is None:
            raise KeyError(f"business registry record missing: {tenant_id}:{business_id}")
        return BusinessProfile(
            business_id=record.business_id,
            region=record.region,
        )


    def channel_identity_snapshot(self, *, tenant_id: str, business_id: str) -> ChannelIdentity:
        record = self.get(tenant_id=tenant_id, business_id=business_id)
        if record is None:
            raise KeyError(f"business registry record missing: {tenant_id}:{business_id}")
        if not record.channel_adapter_key or not record.channel_external_ref:
            raise KeyError(f"channel identity unavailable for legacy business record: {tenant_id}:{business_id}")
        try:
            kind = ChannelKind(record.channel_kind)
        except ValueError as exc:
            raise ValueError(f"unsupported durable channel_kind: {record.channel_kind}") from exc
        identity = ChannelIdentity(
            business_id=record.business_id,
            tenant_id=record.tenant_id,
            channel_kind=kind,
            adapter_key=record.channel_adapter_key,
            external_ref=record.channel_external_ref,
            region=record.region,
            metadata={"registry_version": record.version, "source": "business_registry"},
        )
        identity.validate()
        return identity

    def capability_snapshot(self, *, tenant_id: str, business_id: str) -> RegisteredBusinessCapabilities:
        record = self.get(tenant_id=tenant_id, business_id=business_id)
        if record is None:
            raise KeyError(f"business registry record missing: {tenant_id}:{business_id}")
        return RegisteredBusinessCapabilities(business_id=record.business_id, capabilities=record.capabilities)

    def trust_snapshot(self, *, tenant_id: str, business_id: str) -> BusinessTrustSnapshot:
        record = self.get(tenant_id=tenant_id, business_id=business_id)
        if record is None:
            return BusinessTrustSnapshot(
                business_id=str(business_id),
                trust_tier=BusinessTrustTier.UNKNOWN,
                score=0.0,
                reasons=("No trust profile registered.",),
                metadata={},
            )
        return record.trust


__all__ = [
    "BusinessRegistryRecord",
    "CANON_BUSINESS_LIFECYCLE_EVENT_SPINE_PROJECTION",
    "CANON_BUSINESS_LIFECYCLE_OWNER",
    "CANON_DISTRIBUTED_BUSINESS_REGISTRY",
    "DistributedBusinessRegistry",
    "DistributedDocumentPort",
]
