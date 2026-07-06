"""Codec and row-normalization helpers for delivery-state persistence.

This module intentionally contains no delivery workflow decisions. It only
handles stable JSON/row transformations for the canonical delivery-state owner.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

FINALIZED_PHASE = "finalized"


def metadata_json(metadata: Mapping[str, Any] | None) -> str:
    return json.dumps(dict(metadata or {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def merge_metadata(existing_json: str | None, incoming: Mapping[str, Any] | None) -> dict[str, Any]:
    existing = json.loads(existing_json or "{}") if str(existing_json or "").strip() else {}
    merged = dict(existing or {})
    merged.update(dict(incoming or {}))
    return merged


def normalize_receipt_row(row: Any) -> dict[str, Any]:
    return {
        "message_id": str(row[0]),
        "delivered_at_ms": int(row[1] or 0),
        "external_id": row[2],
        "payload_digest": row[3],
        "metadata": json.loads(row[4] or "{}"),
        "delivery_phase": str(row[5] or FINALIZED_PHASE),
        "accepted_at_ms": None if row[6] is None else int(row[6]),
        "finalized_at_ms": None if row[7] is None else int(row[7]),
    }
