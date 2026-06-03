from __future__ import annotations

from typing import Any
from collections.abc import Mapping

_PLACEHOLDER_IDS = {"", "default", "legacy", "none", "null"}


def best_effort_route_ids(*, payload: Mapping[str, Any], env: Any) -> tuple[str, str]:
    decision = getattr(env, "decision", None)
    decision_id = str(
        (getattr(decision, "decision_id", "") if decision is not None else "")
        or payload.get("decision_id")
        or ""
    )
    correlation_id = str(
        (getattr(decision, "correlation_id", "") if decision is not None else "")
        or payload.get("correlation_id")
        or ""
    )
    return decision_id, correlation_id


def safe_route_blocked_text(label: str) -> str:
    return f"🛑 {str(label).strip()} blocked by route contract."


def safe_runtime_error_text(label: str) -> str:
    return f"❌ {str(label).strip()} error. Попробуйте ещё раз позже или включите безопасный режим."


def blocked_error_payload(*, reason: str, exc: Exception | None = None) -> dict[str, str]:
    payload = {"reason": str(reason)}
    if exc is not None:
        payload["error"] = exc.__class__.__name__
    return payload


def normalized_tenant_id(value: Any, *, fallback: str = "") -> str:
    tenant_id = str(value or "").strip()
    if tenant_id.lower() in _PLACEHOLDER_IDS:
        return str(fallback or "").strip()
    return tenant_id
