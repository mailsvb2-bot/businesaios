from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from boot.bootstrap_config_surface import BootstrapConfigSurface

CANON_AUDIT_STORAGE_POLICY = True


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
class AuditStoragePolicy:
    max_records: int = 5000
    max_bytes: int = 2_000_000
    backup_count: int = 2

    def compact_records(self, records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        snapshot = [dict(item) for item in records]
        if len(snapshot) <= self.max_records:
            return snapshot
        return snapshot[-self.max_records :]

    def should_rotate(self, *, path: Path, serialized_payload: str) -> bool:
        if not path.exists():
            return False
        try:
            current_size = path.stat().st_size
        except OSError:
            return False
        return current_size >= self.max_bytes or len(serialized_payload.encode("utf-8")) >= self.max_bytes


def build_default_audit_storage_policy(*, config_surface: BootstrapConfigSurface | None = None) -> AuditStoragePolicy:
    if config_surface is not None:
        return AuditStoragePolicy(
            max_records=int(config_surface.audit_max_records),
            max_bytes=int(config_surface.audit_max_bytes),
            backup_count=int(config_surface.audit_backup_count),
        )
    return AuditStoragePolicy(
        max_records=_env_int("BUSINESAIOS_AUDIT_MAX_RECORDS", 5000),
        max_bytes=_env_int("BUSINESAIOS_AUDIT_MAX_BYTES", 2_000_000),
        backup_count=_env_int("BUSINESAIOS_AUDIT_BACKUP_COUNT", 2),
    )


def serialize_records_payload(*, records: Iterable[Mapping[str, Any]]) -> str:
    return json.dumps({"records": [dict(item) for item in records]}, ensure_ascii=False, indent=2, sort_keys=True)


def audit_segment_paths(*, path: Path, backup_count: int) -> tuple[Path, ...]:
    candidates = [path.with_suffix(path.suffix + f".{idx}") for idx in range(backup_count, 0, -1)]
    candidates.append(path)
    return tuple(candidate for candidate in candidates if candidate.exists())


def rotate_audit_file(*, path: Path, backup_count: int) -> None:
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


__all__ = [
    "CANON_AUDIT_STORAGE_POLICY",
    "AuditStoragePolicy",
    "build_default_audit_storage_policy",
    "audit_segment_paths",
    "rotate_audit_file",
    "serialize_records_payload",
]
