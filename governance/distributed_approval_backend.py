from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from governance.approval_contract import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStoreContract,
)
from governance.approval_store import _expire_record_if_needed
from governance.persistence_codec import from_dataclass, to_jsonable


CANON_DISTRIBUTED_APPROVAL_BACKEND = True


class ApprovalDocumentPort(Protocol):
    def get(self, *, approval_id: str) -> Mapping[str, Any] | None: ...
    def put(self, *, approval_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int: ...
    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool, limit: int = 100) -> tuple[Mapping[str, Any], ...]: ...


class DistributedApprovalStore(ApprovalStoreContract):
    def __init__(self, backend: ApprovalDocumentPort) -> None:
        self._backend = backend

    def create(self, request: ApprovalRequest) -> ApprovalRecord:
        request.validate()
        if self._backend.get(approval_id=request.approval_id) is not None:
            raise ValueError(f"approval already exists: {request.approval_id}")
        record = ApprovalRecord(request=request, status=ApprovalStatus.REQUESTED, decisions=(), final_reason=None)
        self._backend.put(approval_id=request.approval_id, payload=self._to_payload(record, version=1), expected_version=None)
        return record

    def get(self, approval_id: str) -> ApprovalRecord | None:
        payload = self._backend.get(approval_id=str(approval_id).strip())
        if payload is None:
            return None
        record = self._from_payload(payload)
        normalized, changed = _expire_record_if_needed(record)
        if normalized is None:
            return None
        if changed:
            version = int(payload.get("version") or 0)
            self._backend.put(
                approval_id=normalized.request.approval_id,
                payload=self._to_payload(normalized, version=version + 1),
                expected_version=version,
            )
        return normalized

    def save(self, record: ApprovalRecord) -> ApprovalRecord:
        record.request.validate()
        existing = self._backend.get(approval_id=record.request.approval_id)
        version = 0 if existing is None else int(existing.get("version") or 0)
        self._backend.put(
            approval_id=record.request.approval_id,
            payload=self._to_payload(record, version=version + 1),
            expected_version=None if existing is None else version,
        )
        return record

    def list_open(self, *, tenant_id: str) -> tuple[ApprovalRecord, ...]:
        return self.list_for_tenant(tenant_id=tenant_id, include_terminal=False)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool = True) -> tuple[ApprovalRecord, ...]:
        rows = self._backend.list_for_tenant(tenant_id=str(tenant_id), include_terminal=include_terminal, limit=100)
        items = [self._from_payload(item) for item in rows]
        items.sort(key=lambda row: row.request.created_at)
        return tuple(items)

    @staticmethod
    def _to_payload(record: ApprovalRecord, *, version: int) -> dict[str, Any]:
        return {
            "approval_id": record.request.approval_id,
            "tenant_id": record.request.tenant_id,
            "request": to_jsonable(record.request),
            "status": record.status.value,
            "decisions": [to_jsonable(item) for item in record.decisions],
            "final_reason": record.final_reason,
            "version": int(version),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _from_payload(payload: Mapping[str, Any]) -> ApprovalRecord:
        return ApprovalRecord(
            request=from_dataclass(ApprovalRequest, dict(payload.get("request") or {})),
            status=ApprovalStatus(str(payload.get("status") or ApprovalStatus.REQUESTED.value)),
            decisions=tuple(from_dataclass(ApprovalDecision, dict(item)) for item in list(payload.get("decisions") or []) if isinstance(item, Mapping)),
            final_reason=None if payload.get("final_reason") in (None, "") else str(payload.get("final_reason")),
        )


__all__ = ["CANON_DISTRIBUTED_APPROVAL_BACKEND", "ApprovalDocumentPort", "DistributedApprovalStore"]
