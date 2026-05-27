from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Sequence
from uuid import uuid4

from governance.persistence_codec import atomic_write_json, read_json_or_default
from runtime.execution.region_ownership_plane import RegionRoute, RegionStatePort

CANON_BUSINESS_AUTONOMY_DISTRIBUTED_STATE = True


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileDistributedDocumentStore:
    """Small durable document store with per-process CAS semantics.

    It is intentionally simple: one JSON file per collection, explicit versions,
    and no hidden business logic. Good enough for project-local durable owner-shape.
    """

    def __init__(self, root_dir: Path | str) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def get(self, *, collection: str, document_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            bucket = self._read_collection(collection)
            item = bucket.get(str(document_id).strip())
            return None if item is None else dict(item)

    def put(self, *, collection: str, document_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int:
        doc_id = str(document_id).strip()
        if not doc_id:
            raise ValueError("document_id is required")
        with self._lock:
            bucket = self._read_collection(collection)
            current = bucket.get(doc_id)
            current_version = 0 if current is None else int(current.get("version") or 0)
            if expected_version is not None and current_version != int(expected_version):
                raise ValueError("distributed document version mismatch")
            next_version = current_version + 1
            bucket[doc_id] = {
                **dict(payload),
                "version": next_version,
                "updated_at_utc": str(payload.get("updated_at_utc") or _utc_now_text()),
            }
            self._write_collection(collection, bucket)
            return next_version

    def list_prefix(self, *, collection: str, prefix: str, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        with self._lock:
            bucket = self._read_collection(collection)
            items = [dict(value) for key, value in bucket.items() if str(key).startswith(str(prefix))]
        items.sort(key=lambda row: str(row.get("updated_at_utc") or row.get("updated_at") or ""), reverse=True)
        return tuple(items[: max(1, int(limit))])

    def _collection_path(self, collection: str) -> Path:
        normalized = str(collection).strip().replace("/", "__")
        return self._root_dir / f"{normalized}.json"

    def _read_collection(self, collection: str) -> dict[str, dict[str, Any]]:
        raw = read_json_or_default(self._collection_path(collection), default={"items": {}})
        items = raw.get("items", {}) if isinstance(raw, Mapping) else {}
        return {str(key): dict(value) for key, value in items.items() if isinstance(value, Mapping)}

    def _write_collection(self, collection: str, items: Mapping[str, Mapping[str, Any]]) -> None:
        atomic_write_json(self._collection_path(collection), {"items": {str(k): dict(v) for k, v in items.items()}})


class FileDistributedSequenceStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def next_value(self, *, namespace: str) -> int:
        key = str(namespace).strip()
        if not key:
            raise ValueError("namespace is required")
        with self._lock:
            raw = read_json_or_default(self._path, default={"sequences": {}})
            items = raw.get("sequences", {}) if isinstance(raw, Mapping) else {}
            next_value = int(items.get(key) or 0) + 1
            atomic_write_json(self._path, {"sequences": {**dict(items), key: next_value}})
            return next_value


class FileDistributedCompareAndSwap:
    def __init__(self, documents: FileDistributedDocumentStore, *, collection: str = "cas") -> None:
        self._documents = documents
        self._collection = str(collection).strip() or "cas"

    def create_if_absent(self, *, key: str, payload: Mapping[str, Any], ttl_seconds: int | None = None) -> bool:
        current = self._documents.get(collection=self._collection, document_id=key)
        if current is not None:
            return False
        self._documents.put(collection=self._collection, document_id=key, payload=dict(payload), expected_version=None)
        return True

    def read(self, *, key: str) -> Mapping[str, Any] | None:
        return self._documents.get(collection=self._collection, document_id=key)

    def compare_and_swap(self, *, key: str, expected_version: int, payload: Mapping[str, Any], ttl_seconds: int | None = None) -> bool:
        try:
            self._documents.put(collection=self._collection, document_id=key, payload=dict(payload), expected_version=expected_version)
        except ValueError:
            return False
        return True


class FileDistributedEvidenceAppendPort:
    def __init__(self, root_dir: Path | str) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(self, *, partition_key: str, payload: Mapping[str, Any]) -> str:
        item_id = str(payload.get("evidence_id") or payload.get("event_id") or uuid4())
        with self._lock:
            path = self._partition_path(partition_key)
            raw = read_json_or_default(path, default={"items": []})
            items = list(raw.get("items", []) if isinstance(raw, Mapping) else [])
            items.append({**dict(payload), "_id": item_id})
            atomic_write_json(path, {"items": items})
        return item_id

    def read_partition(self, *, partition_key: str, limit: int = 100, cursor: str | None = None) -> tuple[Sequence[Mapping[str, Any]], str | None]:
        raw = read_json_or_default(self._partition_path(partition_key), default={"items": []})
        items = [dict(item) for item in list(raw.get("items", []) if isinstance(raw, Mapping) else [])]
        items.sort(key=lambda row: str(row.get("created_at") or row.get("emitted_at") or row.get("updated_at_utc") or ""), reverse=True)
        return tuple(items[: max(1, int(limit))]), None

    def read_prefix(self, *, prefix: str, limit: int = 100, cursor: str | None = None) -> tuple[Sequence[Mapping[str, Any]], str | None]:
        rows: list[Mapping[str, Any]] = []
        for path in sorted(self._root_dir.glob("*.json")):
            if not path.stem.startswith(str(prefix).replace("/", "__")):
                continue
            raw = read_json_or_default(path, default={"items": []})
            rows.extend(dict(item) for item in list(raw.get("items", []) if isinstance(raw, Mapping) else []))
        rows.sort(key=lambda row: str(row.get("created_at") or row.get("emitted_at") or row.get("updated_at_utc") or ""), reverse=True)
        return tuple(rows[: max(1, int(limit))]), None

    def _partition_path(self, partition_key: str) -> Path:
        normalized = str(partition_key).strip().replace("/", "__")
        return self._root_dir / f"{normalized}.json"


class FileApprovalDocumentPort:
    def __init__(self, documents: FileDistributedDocumentStore, *, collection: str = "approvals") -> None:
        self._documents = documents
        self._collection = str(collection).strip() or "approvals"

    def get(self, *, approval_id: str) -> Mapping[str, Any] | None:
        return self._documents.get(collection=self._collection, document_id=approval_id)

    def put(self, *, approval_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int:
        return self._documents.put(collection=self._collection, document_id=approval_id, payload=dict(payload), expected_version=expected_version)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool, limit: int = 100) -> tuple[Mapping[str, Any], ...]:
        rows = self._documents.list_prefix(collection=self._collection, prefix="", limit=max(limit * 4, limit))
        result = []
        for row in rows:
            if str(row.get("tenant_id") or "") != str(tenant_id):
                continue
            if not include_terminal and str(row.get("status") or "") in {"approved", "rejected", "cancelled", "expired"}:
                continue
            result.append(dict(row))
            if len(result) >= max(1, int(limit)):
                break
        return tuple(result)


class FileOperatorOverrideDocumentPort:
    def __init__(self, documents: FileDistributedDocumentStore, *, collection: str = "operator_overrides") -> None:
        self._documents = documents
        self._collection = str(collection).strip() or "operator_overrides"

    def get(self, *, override_id: str) -> Mapping[str, Any] | None:
        return self._documents.get(collection=self._collection, document_id=override_id)

    def put(self, *, override_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int:
        return self._documents.put(collection=self._collection, document_id=override_id, payload=dict(payload), expected_version=expected_version)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool, limit: int = 100) -> tuple[Mapping[str, Any], ...]:
        rows = self._documents.list_prefix(collection=self._collection, prefix="", limit=max(limit * 4, limit))
        result = []
        for row in rows:
            if str(row.get("tenant_id") or "") != str(tenant_id):
                continue
            if not include_terminal and str(row.get("status") or "") in {"approved", "rejected", "cancelled", "expired", "consumed"}:
                continue
            result.append(dict(row))
            if len(result) >= max(1, int(limit)):
                break
        return tuple(result)


class FilePlanningMemoryDocumentPort:
    def __init__(self, documents: FileDistributedDocumentStore, *, collection: str = "planning_memory") -> None:
        self._documents = documents
        self._collection = str(collection).strip() or "planning_memory"

    def get(self, *, document_id: str) -> Mapping[str, Any] | None:
        return self._documents.get(collection=self._collection, document_id=document_id)

    def put(self, *, document_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int:
        return self._documents.put(collection=self._collection, document_id=document_id, payload=dict(payload), expected_version=expected_version)


@dataclass(frozen=True)
class FileRegionRouteState(RegionStatePort):
    documents: FileDistributedDocumentStore
    collection: str = "region_routes"
    barriers_collection: str = "region_cutover_barriers"

    def read_route(self, *, tenant_id: str, business_id: str) -> RegionRoute | None:
        payload = self.documents.get(collection=self.collection, document_id=f"{tenant_id}:{business_id}")
        if payload is None:
            return None
        return RegionRoute(
            tenant_id=str(payload.get("tenant_id") or tenant_id),
            business_id=str(payload.get("business_id") or business_id),
            primary_region=str(payload.get("primary_region") or "global"),
            failover_region=str(payload.get("failover_region") or "global"),
            routing_epoch=int(payload.get("routing_epoch") or 0),
            ownership_token=int(payload.get("ownership_token") or 0),
        )

    def compare_and_swap_route(self, *, tenant_id: str, business_id: str, expected_epoch: int | None, route: RegionRoute) -> bool:
        current = self.documents.get(collection=self.collection, document_id=f"{tenant_id}:{business_id}")
        current_epoch = None if current is None else int(current.get("routing_epoch") or 0)
        if expected_epoch != current_epoch:
            return False
        expected_version = None if current is None else int(current.get("version") or 0)
        self.documents.put(
            collection=self.collection,
            document_id=f"{tenant_id}:{business_id}",
            payload={
                "tenant_id": route.tenant_id,
                "business_id": route.business_id,
                "primary_region": route.primary_region,
                "failover_region": route.failover_region,
                "routing_epoch": route.routing_epoch,
                "ownership_token": route.ownership_token,
                "updated_at_utc": _utc_now_text(),
            },
            expected_version=expected_version,
        )
        return True

    def allocate_cutover_barrier(self, *, tenant_id: str, business_id: str, target_region: str) -> str:
        barrier_id = f"barrier:{tenant_id}:{business_id}:{target_region}:{uuid4()}"
        self.documents.put(
            collection=self.barriers_collection,
            document_id=barrier_id,
            payload={
                "tenant_id": tenant_id,
                "business_id": business_id,
                "target_region": target_region,
                "created_at_utc": _utc_now_text(),
            },
            expected_version=None,
        )
        return barrier_id


__all__ = [
    "CANON_BUSINESS_AUTONOMY_DISTRIBUTED_STATE",
    "FileApprovalDocumentPort",
    "FileDistributedCompareAndSwap",
    "FileDistributedDocumentStore",
    "FileDistributedEvidenceAppendPort",
    "FileDistributedSequenceStore",
    "FileOperatorOverrideDocumentPort",
    "FilePlanningMemoryDocumentPort",
    "FileRegionRouteState",
]
