from __future__ import annotations

import logging


def load_world_or_degraded(snapshot_store, snapshot_id: str):
    """Load world snapshot or return degraded placeholder."""
    _log = logging.getLogger(__name__)
    if snapshot_store is None:
        return {"mode": "degraded", "reason": "no_snapshot_store"}
    try:
        raw = snapshot_store.get(str(snapshot_id))
    except (AttributeError, TypeError) as e:
        _log.warning("load_world_or_degraded: snapshot_store.get failed: %s", e)
        return {"mode": "degraded", "reason": "snapshot_error"}
    if raw is None:
        return {"mode": "degraded", "reason": "missing_snapshot"}
    try:
        if isinstance(raw, (bytes, bytearray)):
            import json
            return json.loads(raw.decode("utf-8"))
        return raw
    except (ValueError, UnicodeDecodeError) as e:
        _log.warning("load_world_or_degraded: decode/parse failed: %s", e)
        return {"mode": "degraded", "reason": "snapshot_error"}
