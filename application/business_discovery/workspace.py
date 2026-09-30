from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.business_discovery.contracts import DISCOVERY_FIELDS, DiscoveryFieldSpec
from application.business_discovery.owner_assertion_ingress import (
    OwnerAssertionIngressResult,
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
)
from runtime.state import StateSynthesisEngine
from runtime.state.state_contract import StateFieldRecord, StateSynthesizedSnapshot

CANON_BUSINESS_DISCOVERY_WORKSPACE = True
_NON_COVERING_VALUE_KINDS = frozenset({"absent", "stale"})


@dataclass(frozen=True)
class BusinessDiscoveryProgress:
    total_fields: int
    covered_fields: int
    owner_asserted_fields: int
    remaining_fields: int
    complete: bool
    next_field_key: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_fields": self.total_fields,
            "covered_fields": self.covered_fields,
            "owner_asserted_fields": self.owner_asserted_fields,
            "remaining_fields": self.remaining_fields,
            "complete": self.complete,
            "next_field_key": self.next_field_key,
        }


class BusinessDiscoveryWorkspace:
    """Authenticated workspace projection over canonical discovery owners.

    This class does not own persistence. Writes delegate to
    OwnerBusinessAssertionIngress; reads come from the canonical state snapshot
    store already owned by runtime.state.
    """

    def __init__(
        self,
        *,
        ingress: OwnerBusinessAssertionIngress,
        state_engine: StateSynthesisEngine,
    ) -> None:
        if state_engine.snapshot_store is None:
            raise ValueError("canonical durable StateSnapshotStore is required")
        self._ingress = ingress
        self._state = state_engine

    def describe(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        tenant = _required(tenant_id, "tenant_id")
        business = _required(business_id, "business_id")
        snapshot = self._state.snapshot_store.load_latest(
            tenant_id=tenant,
            business_id=business,
        )
        fields = tuple(
            self._field_view(spec=spec, snapshot=snapshot)
            for spec in DISCOVERY_FIELDS.values()
        )
        progress = _progress(fields)
        return {
            "tenant_id": tenant,
            "business_id": business,
            "state_id": None if snapshot is None else snapshot.state_id,
            "schema_version": "business_discovery_workspace@v1",
            "fields": list(fields),
            "progress": progress.to_dict(),
        }

    def assert_owner(
        self,
        *,
        assertion: OwnerBusinessAssertion,
        idempotency_key: str,
        recorded_at_ms: int | None = None,
    ) -> dict[str, Any]:
        result = self._ingress.ingest(
            assertion=assertion,
            idempotency_key=idempotency_key,
            recorded_at_ms=recorded_at_ms,
        )
        view = self.describe(
            tenant_id=assertion.tenant_id,
            business_id=assertion.business_id,
        )
        view["assertion"] = _result_payload(result)
        return view

    @staticmethod
    def _field_view(
        *,
        spec: DiscoveryFieldSpec,
        snapshot: StateSynthesizedSnapshot | None,
    ) -> dict[str, Any]:
        record = None if snapshot is None else snapshot.fields.get(spec.field_path)
        owner_asserted = _is_owner_asserted(record=record, spec=spec)
        covered = _is_covered(record)
        status = _status(record)
        return {
            "key": spec.key,
            "domain": spec.domain,
            "field_path": spec.field_path,
            "value_kind": spec.value_kind.value,
            "allowed_values": list(spec.allowed_values),
            "legacy_sources": list(spec.legacy_sources),
            "status": status,
            "covered": covered,
            "owner_asserted": owner_asserted,
            "value": None if record is None else record.value,
            "source": None if record is None else record.source,
            "observed_at_ms": None if record is None else record.observed_at_ms,
            "freshness_status": None if record is None else record.freshness_status,
            "conflict": False if record is None else bool(record.conflict),
            "evidence_ids": (
                []
                if record is None
                else [str(item.evidence_id) for item in record.evidence_refs]
            ),
        }


def _required(value: object, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _is_owner_asserted(
    *,
    record: StateFieldRecord | None,
    spec: DiscoveryFieldSpec,
) -> bool:
    if record is None:
        return False
    return (
        str(record.meta.get("business_discovery_field_key") or "") == spec.key
        and str(record.meta.get("epistemic_status") or "") == "OWNER_ASSERTED"
    )


def _is_covered(record: StateFieldRecord | None) -> bool:
    return record is not None and str(record.value_kind) not in _NON_COVERING_VALUE_KINDS


def _status(record: StateFieldRecord | None) -> str:
    if record is None:
        return "missing"
    if bool(record.conflict):
        return "conflict"
    value_kind = str(record.value_kind or "")
    if value_kind == "unknown":
        return "unknown"
    if value_kind in _NON_COVERING_VALUE_KINDS:
        return value_kind
    return "known"


def _progress(fields: tuple[dict[str, Any], ...]) -> BusinessDiscoveryProgress:
    total = len(fields)
    covered = sum(1 for item in fields if bool(item["covered"]))
    owner_asserted = sum(1 for item in fields if bool(item["owner_asserted"]))
    next_key = next(
        (str(item["key"]) for item in fields if not bool(item["covered"])),
        None,
    )
    return BusinessDiscoveryProgress(
        total_fields=total,
        covered_fields=covered,
        owner_asserted_fields=owner_asserted,
        remaining_fields=max(0, total - covered),
        complete=covered == total,
        next_field_key=next_key,
    )


def _result_payload(result: OwnerAssertionIngressResult) -> dict[str, Any]:
    return {
        "fact_id": result.fact_id,
        "evidence_id": result.evidence_id,
        "state_id": result.state_id,
        "field_path": result.field_path,
        "replayed": result.replayed,
    }


__all__ = [
    "CANON_BUSINESS_DISCOVERY_WORKSPACE",
    "BusinessDiscoveryProgress",
    "BusinessDiscoveryWorkspace",
]
