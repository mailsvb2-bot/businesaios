from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from collections.abc import Mapping

from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRecord,
    OperatorOverrideRequest,
    OperatorOverrideStatus,
    OperatorOverrideStoreContract,
)
from execution.operator_override_store import _expire_record_if_needed
from governance.persistence_codec import from_dataclass, to_jsonable


CANON_DISTRIBUTED_OPERATOR_OVERRIDE_BACKEND = True


class OperatorOverrideDocumentPort(Protocol):
    def get(self, *, override_id: str) -> Mapping[str, Any] | None: ...
    def put(self, *, override_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int: ...
    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool, limit: int = 100) -> tuple[Mapping[str, Any], ...]: ...


class DistributedOperatorOverrideStore(OperatorOverrideStoreContract):
    def __init__(self, backend: OperatorOverrideDocumentPort) -> None:
        self._backend = backend

    def create(self, request: OperatorOverrideRequest) -> OperatorOverrideRecord:
        request.validate()
        if self._backend.get(override_id=request.override_id) is not None:
            raise ValueError(f"operator override already exists: {request.override_id}")
        record = OperatorOverrideRecord(request=request, status=OperatorOverrideStatus.REQUESTED)
        self._backend.put(override_id=request.override_id, payload=self._to_payload(record, version=1), expected_version=None)
        return record

    def get(self, override_id: str) -> OperatorOverrideRecord | None:
        payload = self._backend.get(override_id=str(override_id).strip())
        if payload is None:
            return None
        record = self._from_payload(payload)
        normalized, changed = _expire_record_if_needed(record)
        if normalized is None:
            return None
        if changed:
            version = int(payload.get("version") or 0)
            self._backend.put(
                override_id=normalized.request.override_id,
                payload=self._to_payload(normalized, version=version + 1),
                expected_version=version,
            )
        return normalized

    def save(self, record: OperatorOverrideRecord) -> OperatorOverrideRecord:
        record.request.validate()
        existing = self._backend.get(override_id=record.request.override_id)
        version = 0 if existing is None else int(existing.get("version") or 0)
        self._backend.put(
            override_id=record.request.override_id,
            payload=self._to_payload(record, version=version + 1),
            expected_version=None if existing is None else version,
        )
        return record

    def list_open(self, *, tenant_id: str) -> tuple[OperatorOverrideRecord, ...]:
        return self.list_for_tenant(tenant_id=tenant_id, include_terminal=False)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool = True) -> tuple[OperatorOverrideRecord, ...]:
        rows = self._backend.list_for_tenant(tenant_id=str(tenant_id), include_terminal=include_terminal, limit=100)
        items = [self._from_payload(item) for item in rows]
        items.sort(key=lambda row: row.request.requested_at)
        return tuple(items)

    @staticmethod
    def _to_payload(record: OperatorOverrideRecord, *, version: int) -> dict[str, Any]:
        return {
            "override_id": record.request.override_id,
            "tenant_id": record.request.tenant_id,
            "request": to_jsonable(record.request),
            "status": record.status.value,
            "decision": None if record.decision is None else to_jsonable(record.decision),
            "final_reason": record.final_reason,
            "consumed_at": None if record.consumed_at is None else record.consumed_at.isoformat(),
            "consumed_by_execution_id": record.consumed_by_execution_id,
            "version": int(version),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _from_payload(payload: Mapping[str, Any]) -> OperatorOverrideRecord:
        raw_decision = payload.get("decision")
        consumed_at_raw = payload.get("consumed_at")
        return OperatorOverrideRecord(
            request=from_dataclass(OperatorOverrideRequest, dict(payload.get("request") or {})),
            status=OperatorOverrideStatus(str(payload.get("status") or OperatorOverrideStatus.REQUESTED.value)),
            decision=None if not isinstance(raw_decision, Mapping) else from_dataclass(OperatorOverrideDecision, dict(raw_decision)),
            final_reason=None if payload.get("final_reason") in (None, "") else str(payload.get("final_reason")),
            consumed_at=None if consumed_at_raw in (None, "") else datetime.fromisoformat(str(consumed_at_raw)),
            consumed_by_execution_id=None if payload.get("consumed_by_execution_id") in (None, "") else str(payload.get("consumed_by_execution_id")),
        )


__all__ = ["CANON_DISTRIBUTED_OPERATOR_OVERRIDE_BACKEND", "DistributedOperatorOverrideStore", "OperatorOverrideDocumentPort"]
