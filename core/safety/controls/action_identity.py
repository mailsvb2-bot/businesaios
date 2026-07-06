from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

_NOISE_KEYS = frozenset({
    "timestamp",
    "created_at",
    "updated_at",
    "observed_at",
    "trace_id",
    "span_id",
    "request_id",
    "correlation_id",
    "decision_id",
    "run_id",
})


def stable_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in dict(payload or {}).items()
        if str(key) not in _NOISE_KEYS
    }


def canonical_action_id(*, action: str, tenant_id: str, payload: Mapping[str, Any]) -> str:
    data = dict(payload or {})
    explicit = str(
        data.get("action_id")
        or data.get("approval_id")
        or data.get("idempotency_key")
        or ""
    ).strip()
    if explicit:
        return explicit
    material = {
        "tenant_id": str(tenant_id or "unknown"),
        "action": str(action or ""),
        "payload": stable_payload(data),
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"act_{digest}"


def canonical_breaker_key(*, action: str, tenant_id: str) -> str:
    return f"{str(tenant_id or 'unknown')}:{str(action or '')}"
