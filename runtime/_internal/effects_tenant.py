from __future__ import annotations

from typing import Any


def event_log_tenant_id(event_log: Any) -> str:
    """Return the tenant scope exposed by the canonical EventLog contract."""

    tenant_id = str(getattr(event_log, "tenant_id", "") or "").strip()
    if tenant_id:
        return tenant_id
    # Compatibility only for focused effect tests that use tiny fakes.
    return str(getattr(event_log, "_tenant_id", "") or "").strip()


def assert_event_log_tenant(
    event_log: Any,
    *,
    tenant_id: str,
    operation: str,
) -> str:
    requested = str(tenant_id or "").strip()
    if not requested:
        raise RuntimeError("TENANT_ID_REQUIRED")
    bound = event_log_tenant_id(event_log)
    if not bound:
        raise RuntimeError(f"TENANT_CONTEXT_UNBOUND:{operation}")
    if bound != requested:
        raise RuntimeError(
            f"TENANT_CONTEXT_MISMATCH:event_log={bound}:{operation}={requested}"
        )
    return requested


__all__ = ["assert_event_log_tenant", "event_log_tenant_id"]
