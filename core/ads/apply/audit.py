"""Audit event builder for ads apply."""

from __future__ import annotations

import time
from typing import Any

from core.ads.apply.plan_digest import plan_digest


def build_audit_event(
    *,
    tenant_id: str,
    user_id: str,
    kind: str,
    plan: Any,
    status: str,
    detail: dict[str, Any],
    idempotency_key: str,
    reason: str,
    error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": "ads_apply_audit@v1",
        "timestamp_ms": int(time.time() * 1000),
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "payload": {
            "kind": str(kind),
            "status": str(status),
            "reason": str(reason),
            "plan_digest": plan_digest(plan),
            "idempotency_key": str(idempotency_key),
            "error_code": str(error_code) if error_code else None,
            "detail": detail,
        },
        "source": "ads_apply_engine",
    }
