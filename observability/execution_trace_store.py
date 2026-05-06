from __future__ import annotations

CANON_COMPAT_SHIM = True

from runtime.service_names import RuntimeServiceName

import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from boot.bootstrap_config_surface import BootstrapConfigSurface
from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import ensure_parent_dir, to_jsonable
from observability.execution_trace_contract import ExecutionTraceEvent, TraceStage
from observability.storage_coordination import advisory_file_lock
from observability.observability_store_paths import execution_trace_path
from observability.trace_storage_policy import (
    TraceStoragePolicy,
    build_default_trace_storage_policy,
    read_jsonl_segments,
    rotate_trace_file,
    serialize_trace_row,
    trace_segment_paths,
)


CANON_EXECUTION_TRACE_STORE = True



def execution_trace_store_path(*, config_surface=None) -> Path:
    return execution_trace_path(config_surface=config_surface)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class NullExecutionTraceStore:
    def append(self, event: ExecutionTraceEvent) -> None:
        event.validate()

    def list_by_trace(self, *, tenant_id: str, trace_id: str) -> tuple[ExecutionTraceEvent, ...]:
        require_tenant_id(tenant_id)
        return ()

    def list_by_run(self, *, tenant_id: str, run_id: str) -> tuple[ExecutionTraceEvent, ...]:
        require_tenant_id(tenant_id)
        return ()

    def validate_chain(self) -> None:
        return None


class InMemoryExecutionTraceStore:
    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    def append(self, event: ExecutionTraceEvent) -> None:
        event.validate()
        payload = self._canonical_payload(event)
        payload['previous_hash'] = self._rows[-1]['record_hash'] if self._rows else 'GENESIS'
        payload['record_hash'] = self._record_hash(payload)
        self._rows.append(payload)

    def list_by_trace(self, *, tenant_id: str, trace_id: str) -> tuple[ExecutionTraceEvent, ...]:
        tid = require_tenant_id(tenant_id)
        items = [
            self._deserialize(row)
            for row in self._rows
            if row['tenant_id'] == tid and row['trace_id'] == trace_id
        ]
        items.sort(key=lambda x: (x.sequence_no, x.emitted_at))
        return tuple(items)

    def list_by_run(self, *, tenant_id: str, run_id: str) -> tuple[ExecutionTraceEvent, ...]:
        tid = require_tenant_id(tenant_id)
        items = [
            self._deserialize(row)
            for row in self._rows
            if row['tenant_id'] == tid and row['run_id'] == run_id
        ]
        items.sort(key=lambda x: (x.sequence_no, x.emitted_at))
        return tuple(items)

    def validate_chain(self) -> None:
        previous_hash = 'GENESIS'
        for row in self._rows:
            if row.get('previous_hash') != previous_hash:
                raise ValueError('execution trace chain previous_hash mismatch')
            expected_hash = self._record_hash({k: v for k, v in row.items() if k != 'record_hash'})
            if row.get('record_hash') != expected_hash:
                raise ValueError('execution trace chain record_hash mismatch')
            previous_hash = expected_hash

    @staticmethod
    def _canonical_payload(event: ExecutionTraceEvent) -> dict[str, Any]:
        return {str(k): to_jsonable(v) for k, v in asdict(event).items()}

    @staticmethod
    def _record_hash(payload: dict[str, Any]) -> str:
        return _sha256_hex(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    @staticmethod
    def _deserialize(payload: dict[str, Any]) -> ExecutionTraceEvent:
        return ExecutionTraceEvent(
            tenant_id=str(payload['tenant_id']),
            trace_id=str(payload['trace_id']),
            run_id=str(payload['run_id']),
            sequence_no=int(payload['sequence_no']),
            stage=TraceStage(str(payload['stage'])),
            event_type=str(payload['event_type']),
            emitted_at=datetime.fromisoformat(str(payload['emitted_at'])),
            correlation_id=payload.get('correlation_id'),
            decision_id=payload.get('decision_id'),
            action_id=payload.get('action_id'),
            executor_name=payload.get('executor_name'),
            component=payload.get('component'),
            payload=dict(payload.get('payload', {})),
        )


class PersistentExecutionTraceStore:
    def __init__(self, path: str | Path | None = None, *, storage_policy: TraceStoragePolicy | None = None, config_surface: BootstrapConfigSurface | None = None) -> None:
        self._path = Path(path) if path is not None else execution_trace_store_path(config_surface=config_surface)
        self._storage_policy = storage_policy or build_default_trace_storage_policy(config_surface=config_surface)
        ensure_parent_dir(self._path)
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def storage_policy(self) -> TraceStoragePolicy:
        return self._storage_policy

    def append(self, event: ExecutionTraceEvent) -> None:
        event.validate()
        payload = self._canonical_payload(event)
        with advisory_file_lock(self._path, exclusive=True):
            current_segment_rows = self._read_current_segment()
            serialized_payload = serialize_trace_row(row=payload)
            if self._storage_policy.should_rotate(
                path=self._path,
                current_record_count=len(current_segment_rows),
                serialized_payload=serialized_payload,
            ):
                rotate_trace_file(path=self._path, backup_count=self._storage_policy.backup_count)
                current_segment_rows = []
                if not self._path.exists():
                    self._path.touch()
            payload['previous_hash'] = str(current_segment_rows[-1].get('record_hash') or 'GENESIS') if current_segment_rows else 'GENESIS'
            payload['record_hash'] = self._record_hash({k: v for k, v in payload.items()})
            with self._path.open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                fh.write('\n')

    def list_by_trace(self, *, tenant_id: str, trace_id: str) -> tuple[ExecutionTraceEvent, ...]:
        tid = require_tenant_id(tenant_id)
        with advisory_file_lock(self._path, exclusive=False):
            rows = self._read_all_segments()
        items = [
            self._deserialize(row)
            for row in rows
            if row.get('tenant_id') == tid and row.get('trace_id') == trace_id
        ]
        items.sort(key=lambda x: (x.sequence_no, x.emitted_at))
        return tuple(items)

    def list_by_run(self, *, tenant_id: str, run_id: str) -> tuple[ExecutionTraceEvent, ...]:
        tid = require_tenant_id(tenant_id)
        with advisory_file_lock(self._path, exclusive=False):
            rows = self._read_all_segments()
        items = [
            self._deserialize(row)
            for row in rows
            if row.get('tenant_id') == tid and row.get('run_id') == run_id
        ]
        items.sort(key=lambda x: (x.sequence_no, x.emitted_at))
        return tuple(items)

    def validate_chain(self) -> None:
        with advisory_file_lock(self._path, exclusive=False):
            segments = trace_segment_paths(path=self._path, backup_count=self._storage_policy.backup_count)
        for segment in segments:
            previous_hash = 'GENESIS'
            for row in self._read_segment(segment):
                stored_previous = str(row.get('previous_hash') or '')
                stored_hash = str(row.get('record_hash') or '')
                if stored_previous != previous_hash:
                    raise ValueError('execution trace chain previous_hash mismatch')
                expected_hash = self._record_hash({k: v for k, v in row.items() if k != 'record_hash'})
                if stored_hash != expected_hash:
                    raise ValueError('execution trace chain record_hash mismatch')
                previous_hash = stored_hash

    def _read_current_segment(self) -> list[dict[str, Any]]:
        return self._read_segment(self._path)

    def _read_all_segments(self) -> list[dict[str, Any]]:
        return read_jsonl_segments(path=self._path, backup_count=self._storage_policy.backup_count)

    def export_snapshot(self) -> dict[str, Any]:
        with advisory_file_lock(self._path, exclusive=False):
            segments = trace_segment_paths(path=self._path, backup_count=self._storage_policy.backup_count)
        return {
            "path": str(self._path),
            "segment_count": len(segments),
            "segments": tuple(str(item) for item in segments),
        }

    @staticmethod
    def _read_segment(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _canonical_payload(event: ExecutionTraceEvent) -> dict[str, Any]:
        return {str(k): to_jsonable(v) for k, v in asdict(event).items()}

    @staticmethod
    def _record_hash(payload: dict[str, Any]) -> str:
        return _sha256_hex(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    @staticmethod
    def _deserialize(payload: dict[str, Any]) -> ExecutionTraceEvent:
        return ExecutionTraceEvent(
            tenant_id=str(payload['tenant_id']),
            trace_id=str(payload['trace_id']),
            run_id=str(payload['run_id']),
            sequence_no=int(payload['sequence_no']),
            stage=TraceStage(str(payload['stage'])),
            event_type=str(payload['event_type']),
            emitted_at=datetime.fromisoformat(str(payload['emitted_at'])),
            correlation_id=payload.get('correlation_id'),
            decision_id=payload.get('decision_id'),
            action_id=payload.get('action_id'),
            executor_name=payload.get('executor_name'),
            component=payload.get('component'),
            payload=dict(payload.get('payload', {})),
        )


__all__ = [
    'CANON_EXECUTION_TRACE_STORE',
    'InMemoryExecutionTraceStore',
    'NullExecutionTraceStore',
    'PersistentExecutionTraceStore',
    'execution_trace_store_path',
]
