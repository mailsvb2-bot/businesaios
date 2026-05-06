from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import os
import threading

from core.tenancy.normalization import require_tenant_id
from reliability.outbox_backend import (
    CANON_OUTBOX_BACKEND,
    OutboxBackend,
    OutboxBackendHealth,
    OutboxBackendInspector,
    OutboxBackendMode,
    OutboxDeliveryConflict,
    OutboxDeliveryReceipt,
    OutboxDeliveryRecord,
    OutboxDeliveryStatus,
    utc_now,
)
from reliability.outbox_store import OutboxMessage, canonical_payload_digest


CANON_OUTBOX_FILE_BACKEND = True


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unsupported json value: {type(value)!r}")


def _canonical_payload_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=_json_default, separators=(",", ":"))


def _payload_digest(payload: Mapping[str, Any]) -> str:
    return sha256(_canonical_payload_json(payload).encode("utf-8")).hexdigest()


def _safe_segment(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("path segment is required")
    out = []
    for ch in text:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    safe = "".join(out).strip("._")
    if not safe:
        raise ValueError("path segment resolved to empty")
    return safe[:200]


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class FileOutboxBackend(OutboxBackend, OutboxBackendInspector):
    """
    Durable file backend with idempotent message acceptance and drift detection.

    Layout:
      <root>/<tenant>/<topic>/<message_id>.json
    """

    backend_name = "file_outbox_backend"

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def healthcheck(self) -> OutboxBackendHealth:
        healthy = self._root.exists() and self._root.is_dir()
        health = OutboxBackendHealth(
            backend_name=self.backend_name,
            healthy=healthy,
            mode=OutboxBackendMode.DURABLE,
            detail=str(self._root),
        )
        health.validate()
        return health

    def deliver(self, message: OutboxMessage) -> OutboxDeliveryReceipt:
        message.validate()
        tenant_id = require_tenant_id(message.tenant_id)
        digest = message.resolved_payload_digest or canonical_payload_digest(message.payload)
        path = self._message_path(tenant_id=tenant_id, topic=message.topic, message_id=message.message_id)

        with self._lock:
            existing = self.get_record(tenant_id=tenant_id, message_id=message.message_id)
            if existing is not None:
                existing_digest = existing.receipt.payload_digest or ""
                if existing_digest and existing_digest != digest:
                    raise OutboxDeliveryConflict(
                        "outbox file backend detected payload drift for existing message identity",
                        details={
                            "tenant_id": tenant_id,
                            "message_id": message.message_id,
                            "existing_digest": existing_digest,
                            "incoming_digest": digest,
                        },
                    )
                receipt = OutboxDeliveryReceipt(
                    tenant_id=tenant_id,
                    message_id=message.message_id,
                    backend_name=self.backend_name,
                    status=OutboxDeliveryStatus.DUPLICATE,
                    delivered_at=existing.receipt.delivered_at,
                    external_id=existing.receipt.external_id,
                    payload_digest=existing.receipt.payload_digest,
                    metadata=existing.receipt.metadata,
                )
                receipt.validate()
                return receipt

            receipt = OutboxDeliveryReceipt(
                tenant_id=tenant_id,
                message_id=message.message_id,
                backend_name=self.backend_name,
                status=OutboxDeliveryStatus.DELIVERED,
                delivered_at=utc_now(),
                external_id=str(path),
                payload_digest=digest,
                metadata={
                    "topic": message.topic,
                    "dedupe_key": message.dedupe_key,
                    "trace_id": message.trace_id,
                    "run_id": message.run_id,
                    "decision_id": message.decision_id,
                },
            )
            receipt.validate()
            record = OutboxDeliveryRecord(
                receipt=receipt,
                topic=message.topic,
                dedupe_key=message.dedupe_key,
                payload=dict(message.payload),
            )
            record.validate()

            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(path.suffix + ".tmp")
            serialized = json.dumps(self._record_to_row(record), ensure_ascii=False, sort_keys=True, default=_json_default)
            try:
                with temp_path.open("w", encoding="utf-8") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
                temp_path.replace(path)
                _fsync_directory(path.parent)
                if path.parent != self._root:
                    _fsync_directory(self._root)
            finally:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
            return receipt

    def get_receipt(self, *, tenant_id: str, message_id: str) -> OutboxDeliveryReceipt | None:
        record = self.get_record(tenant_id=tenant_id, message_id=message_id)
        return None if record is None else record.receipt

    def get_record(self, *, tenant_id: str, message_id: str) -> OutboxDeliveryRecord | None:
        tid = require_tenant_id(tenant_id)
        safe_message_id = _safe_segment(str(message_id))
        with self._lock:
            for path in self._root.glob(f"{_safe_segment(tid)}/**/{safe_message_id}.json"):
                row = json.loads(path.read_text(encoding="utf-8"))
                return self._row_to_record(row)
        return None

    def list_records(
        self,
        *,
        tenant_id: str,
        topic: str | None = None,
        limit: int = 100,
    ) -> tuple[OutboxDeliveryRecord, ...]:
        tid = _safe_segment(require_tenant_id(tenant_id))
        base = self._root / tid
        if topic:
            base = base / _safe_segment(str(topic))
        if not base.exists():
            return ()
        records: list[OutboxDeliveryRecord] = []
        with self._lock:
            for path in sorted(base.rglob("*.json")):
                row = json.loads(path.read_text(encoding="utf-8"))
                records.append(self._row_to_record(row))
                if len(records) >= max(1, int(limit)):
                    break
        return tuple(records)

    def _message_path(self, *, tenant_id: str, topic: str, message_id: str) -> Path:
        return self._root / _safe_segment(tenant_id) / _safe_segment(topic) / f"{_safe_segment(message_id)}.json"

    @staticmethod
    def _record_to_row(record: OutboxDeliveryRecord) -> dict[str, Any]:
        record.validate()
        row = asdict(record)
        row["receipt"]["status"] = record.receipt.status.value
        row["receipt"]["delivered_at"] = record.receipt.delivered_at.isoformat()
        row["payload"] = dict(record.payload)
        row["receipt"]["metadata"] = dict(record.receipt.metadata)
        return row

    @staticmethod
    def _row_to_record(row: Mapping[str, Any]) -> OutboxDeliveryRecord:
        receipt_row = dict(row["receipt"])
        receipt = OutboxDeliveryReceipt(
            tenant_id=str(receipt_row["tenant_id"]),
            message_id=str(receipt_row["message_id"]),
            backend_name=str(receipt_row["backend_name"]),
            status=OutboxDeliveryStatus(str(receipt_row["status"])),
            delivered_at=datetime.fromisoformat(str(receipt_row["delivered_at"])),
            external_id=receipt_row.get("external_id"),
            payload_digest=receipt_row.get("payload_digest"),
            metadata=dict(receipt_row.get("metadata") or {}),
        )
        record = OutboxDeliveryRecord(
            receipt=receipt,
            topic=str(row["topic"]),
            dedupe_key=str(row["dedupe_key"]),
            payload=dict(row.get("payload") or {}),
        )
        record.validate()
        return record


__all__ = [
    "CANON_OUTBOX_BACKEND",
    "CANON_OUTBOX_FILE_BACKEND",
    "FileOutboxBackend",
]
