from __future__ import annotations

CANON_COMPAT_SHIM = True

from pathlib import Path
from typing import Any

from observability.audit_storage_policy import audit_segment_paths
from observability.trace_storage_policy import trace_segment_paths

CANON_OBSERVABILITY_EXPORT_MANIFEST = True


def _segment_payload(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        "path": str(path),
        "filename": path.name,
        "bytes": int(size),
        "exists": path.exists(),
    }


def build_observability_export_manifest(*, stores: dict[str, object]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name, store in stores.items():
        path = getattr(store, "path", None)
        if path is None:
            payload[name] = {"backend": type(store).__name__, "segments": ()}
            continue
        backup_count = int(getattr(getattr(store, "storage_policy", None), "backup_count", 0) or 0)
        path_obj = Path(path)
        if path_obj.suffix == ".jsonl":
            segments = trace_segment_paths(path=path_obj, backup_count=backup_count)
        else:
            segments = audit_segment_paths(path=path_obj, backup_count=backup_count)
        payload[name] = {
            "backend": type(store).__name__,
            "path": str(path_obj),
            "segments": tuple(_segment_payload(item) for item in segments),
        }
    return payload


__all__ = ["CANON_OBSERVABILITY_EXPORT_MANIFEST", "build_observability_export_manifest"]
