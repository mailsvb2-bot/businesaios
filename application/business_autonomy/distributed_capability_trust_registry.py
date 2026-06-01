from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any, Mapping, Protocol, Sequence

from application.business_autonomy.contracts import BusinessCapability, CapabilityKind
from application.business_autonomy.registry import RegisteredBusinessCapabilities
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier
from core.tenancy.normalization import require_tenant_id

CANON_DISTRIBUTED_BUSINESS_REGISTRY = True


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
            version=max(0, int(payload.get("version") or 0)),
            updated_at_utc=str(payload.get("updated_at_utc") or ""),
        )
        record.validate()
        return record


class DistributedBusinessRegistry:
    def __init__(self, *, documents: DistributedDocumentPort, collection: str = "business_registry") -> None:
        self._documents = documents
        self._collection = str(collection).strip() or "business_registry"

    def register_or_update(self, record: BusinessRegistryRecord) -> BusinessRegistryRecord:
        record.validate()
        existing_payload = self._documents.get(collection=self._collection, document_id=record.document_id)
        existing_version = 0 if existing_payload is None else int(existing_payload.get("version") or 0)
        if existing_payload is not None:
            existing = BusinessRegistryRecord.from_dict(existing_payload)
            if existing.tenant_id != record.tenant_id:
                raise ValueError("business registry tenant reassignment is forbidden")
            if existing.ownership_key != record.ownership_key:
                raise ValueError("business registry ownership_key reassignment is forbidden")
        stamped = BusinessRegistryRecord(
            business_id=record.business_id,
            tenant_id=record.tenant_id,
            ownership_key=record.ownership_key,
            region=record.region,
            channel_kind=record.channel_kind,
            capabilities=tuple(record.capabilities),
            trust=record.trust,
            governance_enabled=bool(record.governance_enabled),
            persistent_surfaces=tuple(sorted({str(item) for item in record.persistent_surfaces if str(item).strip()})),
            version=existing_version + 1,
            updated_at_utc=datetime.now(UTC).isoformat(),
        )
        persisted_version = self._documents.put(
            collection=self._collection,
            document_id=stamped.document_id,
            payload=stamped.to_dict(),
            expected_version=None if existing_payload is None else existing_version,
        )
        return BusinessRegistryRecord.from_dict({**stamped.to_dict(), "version": persisted_version})

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
    "CANON_DISTRIBUTED_BUSINESS_REGISTRY",
    "DistributedBusinessRegistry",
    "DistributedDocumentPort",
]
