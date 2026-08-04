"""Correlation helpers for runtime execution."""

from __future__ import annotations

import json


def extract_correlation_key(snapshot_store, snapshot_id: str) -> str | None:
    """Read a correlation key while exposing snapshot-store availability failures."""

    if snapshot_store is None or not hasattr(snapshot_store, "get"):
        return None
    raw = snapshot_store.get(str(snapshot_id))
    if not raw or not isinstance(raw, bytes | bytearray):
        return None
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict):
        return None
    meta = obj.get("meta")
    if not isinstance(meta, dict):
        return None
    ck = meta.get("correlation_key") or meta.get("correlation")
    return str(ck) if ck else None
