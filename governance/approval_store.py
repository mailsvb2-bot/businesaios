from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import os

from core.tenancy.normalization import require_tenant_id
from governance.approval_contract import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStoreContract,
    utc_now,
)
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from governance.persistence_paths import approval_store_path


CANON_GOVERNANCE_APPROVAL_STORE = True


def _expire_record_if_needed(record: ApprovalRecord | None) -> tuple[ApprovalRecord | None, bool]:
    if record is None:
        return None, False
    if record.is_terminal:
        return record, False
    if record.request.expires_at is None:
        return record, False
    if utc_now() <= record.request.expires_at:
        return record, False
    return replace(record, status=ApprovalStatus.EXPIRED, final_reason='expired'), True


class InMemoryApprovalStore(ApprovalStoreContract):
    def __init__(self) -> None:
        self._items: dict[str, ApprovalRecord] = {}

    def _normalize_items(self) -> None:
        for approval_id, record in list(self._items.items()):
            normalized, expired = _expire_record_if_needed(record)
            if normalized is not None and expired:
                self._items[approval_id] = normalized

    def create(self, request: ApprovalRequest) -> ApprovalRecord:
        request.validate()
        if request.approval_id in self._items:
            raise ValueError(f"approval already exists: {request.approval_id}")
        record = ApprovalRecord(
            request=request,
            status=ApprovalStatus.REQUESTED,
            decisions=(),
            final_reason=None,
        )
        self._items[request.approval_id] = record
        return record

    def get(self, approval_id: str) -> ApprovalRecord | None:
        key = str(approval_id or '').strip()
        record, changed = _expire_record_if_needed(self._items.get(key))
        if record is not None and changed:
            self._items[key] = record
        return record

    def save(self, record: ApprovalRecord) -> ApprovalRecord:
        record.request.validate()
        self._items[record.request.approval_id] = replace(record)
        return record

    def list_open(self, *, tenant_id: str) -> tuple[ApprovalRecord, ...]:
        return self.list_for_tenant(tenant_id=tenant_id, include_terminal=False)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool = True) -> tuple[ApprovalRecord, ...]:
        tid = require_tenant_id(tenant_id)
        self._normalize_items()
        items = [
            record
            for record in self._items.values()
            if record.request.tenant_id == tid and (include_terminal or not record.is_terminal)
        ]
        items.sort(key=lambda x: x.request.created_at)
        return tuple(items)


class PersistentApprovalStore(ApprovalStoreContract):
    """Durable file-backed approval store.

    Stores only approval state snapshots. It must not contain approval logic.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else approval_store_path()
        self._items: dict[str, ApprovalRecord] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _normalize_items(self) -> bool:
        changed = False
        for approval_id, record in list(self._items.items()):
            normalized, expired = _expire_record_if_needed(record)
            if normalized is not None and expired:
                self._items[approval_id] = normalized
                changed = True
        return changed

    def create(self, request: ApprovalRequest) -> ApprovalRecord:
        request.validate()
        if request.approval_id in self._items:
            raise ValueError(f"approval already exists: {request.approval_id}")
        record = ApprovalRecord(
            request=request,
            status=ApprovalStatus.REQUESTED,
            decisions=(),
            final_reason=None,
        )
        self._items[request.approval_id] = record
        self._flush()
        return record

    def get(self, approval_id: str) -> ApprovalRecord | None:
        key = str(approval_id or '').strip()
        record, changed = _expire_record_if_needed(self._items.get(key))
        if record is not None and changed:
            self._items[key] = record
            self._flush()
        return record

    def save(self, record: ApprovalRecord) -> ApprovalRecord:
        record.request.validate()
        self._items[record.request.approval_id] = replace(record)
        self._flush()
        return record

    def list_open(self, *, tenant_id: str) -> tuple[ApprovalRecord, ...]:
        return self.list_for_tenant(tenant_id=tenant_id, include_terminal=False)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool = True) -> tuple[ApprovalRecord, ...]:
        tid = require_tenant_id(tenant_id)
        if self._normalize_items():
            self._flush()
        items = [
            record
            for record in self._items.values()
            if record.request.tenant_id == tid and (include_terminal or not record.is_terminal)
        ]
        items.sort(key=lambda x: x.request.created_at)
        return tuple(items)

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"records": []})
        records = raw.get("records", []) if isinstance(raw, dict) else []
        loaded: dict[str, ApprovalRecord] = {}
        for item in records:
            record = self._record_from_payload(item)
            loaded[record.request.approval_id] = record
        self._items = loaded

    def _flush(self) -> None:
        atomic_write_json(
            self._path,
            {"records": [self._record_to_payload(item) for item in self._items.values()]},
        )

    @staticmethod
    def _record_to_payload(record: ApprovalRecord) -> dict[str, object]:
        return {
            "request": to_jsonable(record.request),
            "status": record.status.value,
            "decisions": [to_jsonable(item) for item in record.decisions],
            "final_reason": record.final_reason,
        }

    @staticmethod
    def _record_from_payload(payload: dict[str, object]) -> ApprovalRecord:
        request = from_dataclass(ApprovalRequest, dict(payload.get("request", {})))
        decisions = tuple(
            from_dataclass(ApprovalDecision, item)
            for item in payload.get("decisions", [])
        )
        return ApprovalRecord(
            request=request,
            status=ApprovalStatus(payload.get("status", ApprovalStatus.REQUESTED.value)),
            decisions=decisions,
            final_reason=payload.get("final_reason"),
        )


def build_default_approval_store() -> ApprovalStoreContract:
    mode = os.getenv("BUSINESAIOS_APPROVAL_STORE_BACKEND", "file").strip().lower()
    if mode == "memory":
        return InMemoryApprovalStore()
    return PersistentApprovalStore()


__all__ = [
    "CANON_GOVERNANCE_APPROVAL_STORE",
    "InMemoryApprovalStore",
    "PersistentApprovalStore",
    "build_default_approval_store",
]
