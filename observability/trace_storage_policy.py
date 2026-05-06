from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from boot.bootstrap_config_surface import BootstrapConfigSurface

CANON_TRACE_STORAGE_POLICY = True


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class TraceStoragePolicy:
    max_records_per_segment: int = 10000
    max_bytes_per_segment: int = 5_000_000
    backup_count: int = 4

    def should_rotate(self, *, path: Path, current_record_count: int, serialized_payload: str) -> bool:
        if current_record_count >= self.max_records_per_segment:
            return True
        if not path.exists():
            return False
        try:
            current_size = path.stat().st_size
        except OSError:
            return False
        return current_size >= self.max_bytes_per_segment or len(serialized_payload.encode("utf-8")) >= self.max_bytes_per_segment


def build_default_trace_storage_policy(*, config_surface: BootstrapConfigSurface | None = None) -> TraceStoragePolicy:
    if config_surface is not None:
        return TraceStoragePolicy(
            max_records_per_segment=int(config_surface.trace_max_records),
            max_bytes_per_segment=int(config_surface.trace_max_bytes),
            backup_count=int(config_surface.trace_backup_count),
        )
    return TraceStoragePolicy(
        max_records_per_segment=_env_int("BUSINESAIOS_TRACE_MAX_RECORDS", 10000),
        max_bytes_per_segment=_env_int("BUSINESAIOS_TRACE_MAX_BYTES", 5_000_000),
        backup_count=_env_int("BUSINESAIOS_TRACE_BACKUP_COUNT", 4),
    )


def serialize_trace_row(*, row: Mapping[str, Any]) -> str:
    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True)


def rotate_trace_file(*, path: Path, backup_count: int) -> None:
    if backup_count <= 0 or not path.exists():
        return
    oldest = path.with_suffix(path.suffix + f".{backup_count}")
    if oldest.exists():
        oldest.unlink()
    for idx in range(backup_count - 1, 0, -1):
        candidate = path.with_suffix(path.suffix + f".{idx}")
        if candidate.exists():
            candidate.replace(path.with_suffix(path.suffix + f".{idx + 1}"))
    path.replace(path.with_suffix(path.suffix + ".1"))


def trace_segment_paths(*, path: Path, backup_count: int) -> tuple[Path, ...]:
    candidates = [path.with_suffix(path.suffix + f".{idx}") for idx in range(backup_count, 0, -1)]
    candidates.append(path)
    return tuple(candidate for candidate in candidates if candidate.exists())


def read_jsonl_segments(*, path: Path, backup_count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in trace_segment_paths(path=path, backup_count=backup_count):
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


__all__ = [
    "CANON_TRACE_STORAGE_POLICY",
    "TraceStoragePolicy",
    "build_default_trace_storage_policy",
    "rotate_trace_file",
    "serialize_trace_row",
    "trace_segment_paths",
    "read_jsonl_segments",
]
