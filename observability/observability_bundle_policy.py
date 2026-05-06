from __future__ import annotations

CANON_COMPAT_SHIM = True

import hashlib
import json
from typing import Any, Mapping

CANON_OBSERVABILITY_BUNDLE_POLICY = True


def payload_sha256(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_observability_bundle_metadata(*, stores: Mapping[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(stores, ensure_ascii=False, sort_keys=True)
    segment_count = 0
    existing_segments = 0
    total_bytes = 0
    for entry in stores.values():
        segments = entry.get("segments", ()) if isinstance(entry, dict) else ()
        segment_count += len(segments)
        for segment in segments:
            if isinstance(segment, dict):
                total_bytes += int(segment.get("bytes", 0) or 0)
                if segment.get("exists"):
                    existing_segments += 1
    return {
        "store_count": len(stores),
        "segment_count": segment_count,
        "existing_segment_count": existing_segments,
        "total_bytes": total_bytes,
        "stores_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    }


def build_record_bundle_metadata(*, records: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "payload_sha256": payload_sha256(records),
        "field_count": len(records),
    }


__all__ = [
    "CANON_OBSERVABILITY_BUNDLE_POLICY",
    "build_observability_bundle_metadata",
    "build_record_bundle_metadata",
    "payload_sha256",
]
