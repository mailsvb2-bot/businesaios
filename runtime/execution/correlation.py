from __future__ import annotations

"""Correlation helpers for runtime execution."""


def extract_correlation_key(snapshot_store, snapshot_id: str) -> str | None:
    """Best-effort correlation_key extraction from WorldState snapshot.

    Executor can recover it by reading the signed snapshot referenced by the decision.
    This is read-only and must never break execution.
    """

    try:
        if snapshot_store is None or not hasattr(snapshot_store, "get"):
            return None
        raw = snapshot_store.get(str(snapshot_id))
        if not raw:
            return None
        import json

        obj = json.loads(raw.decode("utf-8")) if isinstance(raw, bytes | bytearray) else None
        if not isinstance(obj, dict):
            return None
        meta = obj.get("meta")
        if not isinstance(meta, dict):
            return None
        ck = meta.get("correlation_key") or meta.get("correlation")
        return str(ck) if ck else None
    except Exception:
        return None
