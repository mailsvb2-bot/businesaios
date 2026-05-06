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
from core.tenancy.normalization import require_tenant_id
from observability.audit_storage_policy import AuditStoragePolicy, build_default_audit_storage_policy, rotate_audit_file, serialize_records_payload
from observability.storage_coordination import advisory_file_lock
from observability.observability_store_paths import action_audit_path
from shared.types import ensure_jsonable


CANON_ACTION_AUDIT_LOG = True


def action_audit_log_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    path = action_audit_path(config_surface=config_surface)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".action_audit_", suffix=".json", dir=str(path.parent))
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
class ActionAuditLog:
    records: List[Dict[str, Any]] = field(default_factory=list)
    storage_policy: AuditStoragePolicy = field(default_factory=build_default_audit_storage_policy)

    def record(self, record: Dict[str, Any]) -> None:
        payload = dict(ensure_jsonable(record or {}))
        tenant_id = payload.get("tenant_id")
        if tenant_id is not None and str(tenant_id).strip():
            payload["tenant_id"] = require_tenant_id(str(tenant_id))
        payload.setdefault("kind", "action")
        payload.setdefault("recorded_at", utc_now_iso())
        self.records.append(payload)
        self.records = self.storage_policy.compact_records(self.records)

    def record_stage(self, *, tenant_id: str, action_id: str, action_type: str, stage: str, status: str, trace_id: str | None = None, decision_id: str | None = None, correlation_id: str | None = None, run_id: str | None = None, payload: Mapping[str, Any] | None = None) -> None:
        self.record({
            "tenant_id": require_tenant_id(tenant_id),
            "action_id": str(action_id),
            "action_type": str(action_type),
            "status": str(status),
            "trace_id": None if trace_id is None else str(trace_id),
            "decision_id": None if decision_id is None else str(decision_id),
            "correlation_id": None if correlation_id is None else str(correlation_id),
            "run_id": None if run_id is None else str(run_id),
            "payload": {"stage": str(stage), **dict(ensure_jsonable(payload or {}))},
        })

    def record_execution(self, *, tenant_id: str, action_id: str, action_type: str, status: str, trace_id: str | None = None, payload: Mapping[str, Any] | None = None) -> None:
        self.record({
            "tenant_id": str(tenant_id),
            "action_id": str(action_id),
            "action_type": str(action_type),
            "status": str(status),
            "trace_id": None if trace_id is None else str(trace_id),
            "payload": dict(ensure_jsonable(payload or {})),
        })

    def record_inference_selection(
        self,
        *,
        tenant_id: str,
        action_id: str,
        action_type: str,
        provider_name: str,
        capacity_tier: str,
        estimated_cost_usd: float,
        trace_id: str | None = None,
        decision_id: str | None = None,
        correlation_id: str | None = None,
        run_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        self.record_stage(
            tenant_id=require_tenant_id(tenant_id),
            action_id=str(action_id),
            action_type=str(action_type),
            stage='inference.capacity_selection',
            status='selected',
            trace_id=None if trace_id is None else str(trace_id),
            decision_id=None if decision_id is None else str(decision_id),
            correlation_id=None if correlation_id is None else str(correlation_id),
            run_id=None if run_id is None else str(run_id),
            payload={
                'provider_name': str(provider_name),
                'capacity_tier': str(capacity_tier),
                'estimated_cost_usd': round(float(estimated_cost_usd), 6),
                'economic_policy_guarded': True,
                **dict(ensure_jsonable(payload or {})),
            },
        )

    def record_inference_verification(
        self,
        *,
        tenant_id: str,
        action_id: str,
        action_type: str,
        provider_name: str,
        accepted: bool,
        verification_reason: str,
        trace_id: str | None = None,
        decision_id: str | None = None,
        correlation_id: str | None = None,
        run_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        self.record_stage(
            tenant_id=require_tenant_id(tenant_id),
            action_id=str(action_id),
            action_type=str(action_type),
            stage='inference.verification',
            status='accepted' if accepted else 'rejected',
            trace_id=None if trace_id is None else str(trace_id),
            decision_id=None if decision_id is None else str(decision_id),
            correlation_id=None if correlation_id is None else str(correlation_id),
            run_id=None if run_id is None else str(run_id),
            payload={
                'provider_name': str(provider_name),
                'accepted': bool(accepted),
                'verification_reason': str(verification_reason),
                **dict(ensure_jsonable(payload or {})),
            },
        )

    def latest(self) -> Dict[str, Any] | None:
        return dict(self.records[-1]) if self.records else None

    def latest_by_action(self, *, action_id: str) -> Dict[str, Any] | None:
        needle = str(action_id)
        for item in reversed(self.records):
            if str(item.get("action_id") or "") == needle:
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

    def list_by_tenant(self, *, tenant_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        required_tenant_id = require_tenant_id(tenant_id)
        out: list[dict[str, Any]] = []
        for item in reversed(self.records):
            if str(item.get("tenant_id") or "") == required_tenant_id:
                out.append(dict(item))
                if len(out) >= max(0, int(limit)):
                    break
        return out

    def latest_by_trace(self, *, trace_id: str) -> Dict[str, Any] | None:
        rows = self.list_by_trace(trace_id=trace_id, limit=1)
        return dict(rows[0]) if rows else None


class FileActionAuditLog(ActionAuditLog):
    def __init__(self, path: str | Path | None = None, *, storage_policy: AuditStoragePolicy | None = None, config_surface: BootstrapConfigSurface | None = None) -> None:
        self._path = Path(path) if path is not None else action_audit_log_path(config_surface=config_surface)
        super().__init__(records=[], storage_policy=storage_policy or build_default_audit_storage_policy(config_surface=config_surface))
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def record(self, record: Dict[str, Any]) -> None:
        super().record(record)
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
            self.records = [dict(item) for item in records or [] if isinstance(item, dict)]

    def _flush(self) -> None:
        with advisory_file_lock(self._path, exclusive=True):
            self.records = self.storage_policy.compact_records(self.records)
            serialized = serialize_records_payload(records=self.records)
            if self.storage_policy.should_rotate(path=self._path, serialized_payload=serialized):
                rotate_audit_file(path=self._path, backup_count=self.storage_policy.backup_count)
            _atomic_write_json(self._path, {"records": list(self.records)})


def build_default_action_audit_log(*, config_surface: BootstrapConfigSurface | None = None, storage_policy: AuditStoragePolicy | None = None) -> ActionAuditLog:
    mode = (config_surface.action_audit_backend if config_surface is not None else os.getenv("BUSINESAIOS_ACTION_AUDIT_LOG_BACKEND", "file")).strip().lower()
    if mode == "memory":
        return ActionAuditLog(storage_policy=storage_policy or build_default_audit_storage_policy(config_surface=config_surface))
    return FileActionAuditLog(path=action_audit_log_path(config_surface=config_surface), storage_policy=storage_policy, config_surface=config_surface)


__all__ = ["CANON_ACTION_AUDIT_LOG", "ActionAuditLog", "FileActionAuditLog", "action_audit_log_path", "build_default_action_audit_log"]
