from __future__ import annotations

CANON_COMPAT_SHIM = True

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

from boot.bootstrap_config_surface import BootstrapConfigSurface
from kernel.decision_result import DecisionResult
from observability.audit_storage_policy import AuditStoragePolicy, build_default_audit_storage_policy, rotate_audit_file, serialize_records_payload
from observability.storage_coordination import advisory_file_lock
from observability.observability_store_paths import decision_audit_path
from shared.types import ensure_jsonable


CANON_DECISION_AUDIT_LOG = True


def decision_audit_log_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    path = decision_audit_path(config_surface=config_surface)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".decision_audit_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DecisionAuditLog:
    records: List[Dict[str, Any]] = field(default_factory=list)
    storage_policy: AuditStoragePolicy = field(default_factory=build_default_audit_storage_policy)

    def record(self, decision_result: DecisionResult) -> None:
        record = dict(ensure_jsonable(decision_result.as_dict()))
        record["kind"] = "decision"
        record.setdefault("recorded_at", utc_now_iso())
        self.records.append(record)
        self.records = self.storage_policy.compact_records(self.records)

    def record_payload(self, payload: Mapping[str, Any]) -> None:
        record = dict(ensure_jsonable(payload or {}))
        record["kind"] = "decision"
        record.setdefault("recorded_at", utc_now_iso())
        self.records.append(record)
        self.records = self.storage_policy.compact_records(self.records)

    def latest(self) -> Dict[str, Any] | None:
        return dict(self.records[-1]) if self.records else None

    def latest_by_decision_id(self, *, decision_id: str) -> Dict[str, Any] | None:
        needle = str(decision_id)
        for item in reversed(self.records):
            if str(item.get("decision_id") or item.get("id") or "") == needle:
                return dict(item)
        return None

    def list_by_trace(self, *, trace_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        needle = str(trace_id)
        out: list[dict[str, Any]] = []
        for item in reversed(self.records):
            if str(item.get("trace_id") or "") == needle:
                out.append(dict(item))
                if len(out) >= max(0, int(limit)):
                    break
        return out

    def latest_by_trace(self, *, trace_id: str) -> Dict[str, Any] | None:
        rows = self.list_by_trace(trace_id=trace_id, limit=1)
        return dict(rows[0]) if rows else None


class FileDecisionAuditLog(DecisionAuditLog):
    def __init__(self, path: str | Path | None = None, *, storage_policy: AuditStoragePolicy | None = None, config_surface: BootstrapConfigSurface | None = None) -> None:
        self._path = Path(path) if path is not None else decision_audit_log_path(config_surface=config_surface)
        super().__init__(records=[], storage_policy=storage_policy or build_default_audit_storage_policy(config_surface=config_surface))
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def record(self, decision_result: DecisionResult) -> None:
        super().record(decision_result)
        self._flush()

    def record_payload(self, payload: Mapping[str, Any]) -> None:
        super().record_payload(payload)
        self._flush()

    def _load(self) -> None:
        with advisory_file_lock(self._path, exclusive=False):
            if not self._path.exists():
                return
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            records = payload.get("records") if isinstance(payload, dict) else []
            self.records = self.storage_policy.compact_records([dict(item) for item in records or [] if isinstance(item, dict)])

    def _flush(self) -> None:
        with advisory_file_lock(self._path, exclusive=True):
            self.records = self.storage_policy.compact_records(self.records)
            serialized = serialize_records_payload(records=self.records)
            if self.storage_policy.should_rotate(path=self._path, serialized_payload=serialized):
                rotate_audit_file(path=self._path, backup_count=self.storage_policy.backup_count)
            _atomic_write_json(self._path, {"records": list(self.records)})


def build_default_decision_audit_log(*, config_surface: BootstrapConfigSurface | None = None, storage_policy: AuditStoragePolicy | None = None) -> DecisionAuditLog:
    mode = (config_surface.decision_audit_backend if config_surface is not None else os.getenv("BUSINESAIOS_DECISION_AUDIT_LOG_BACKEND", "file")).strip().lower()
    if mode == "memory":
        return DecisionAuditLog(storage_policy=storage_policy or build_default_audit_storage_policy(config_surface=config_surface))
    return FileDecisionAuditLog(path=decision_audit_log_path(config_surface=config_surface), storage_policy=storage_policy, config_surface=config_surface)


__all__ = ["CANON_DECISION_AUDIT_LOG", "DecisionAuditLog", "FileDecisionAuditLog", "decision_audit_log_path", "build_default_decision_audit_log"]
