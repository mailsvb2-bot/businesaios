from __future__ import annotations

from typing import Any

from execution.runtime_keys import OBSERVABILITY_KEY
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.common.connector_support import LIVE_MODE, STUB_MODE

CANON_CONNECTOR_TRUTH = True


def connector_truth_payload(
    *,
    connector_name: str,
    configured: bool,
    capabilities: ConnectorCapabilities,
    operation: str,
    dry_run: bool,
    idempotency_key: str | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = dict(payload or {})
    mode = LIVE_MODE if bool(configured) else STUB_MODE
    existing.setdefault("operation", str(operation))
    existing.setdefault("connector_name", str(connector_name))
    existing.setdefault("mode", mode)
    existing.setdefault("configured", bool(configured))
    existing.setdefault("dry_run", bool(dry_run))
    if idempotency_key:
        existing.setdefault("idempotency_key", str(idempotency_key))
    caps = capabilities.as_dict()
    maturity = str((caps.get("metadata") or {}).get("maturity") or ConnectorMaturity.PLACEHOLDER.value)
    existing.setdefault("capabilities", caps)
    existing.setdefault("maturity", maturity)
    existing.setdefault("production_ready", bool(configured and caps.get("write") and caps.get("verify") and maturity == ConnectorMaturity.REAL.value))
    trace_context = {
        "trace_id": str(existing.get("trace_id") or existing.get("correlation_id") or ""),
        "correlation_id": str(existing.get("correlation_id") or existing.get("trace_id") or ""),
    }
    existing.setdefault("trace_context", trace_context)
    existing.setdefault(OBSERVABILITY_KEY, dict(trace_context))
    existing.setdefault(
        "truth_layer",
        {
            "implemented": bool(configured),
            "stub": mode == STUB_MODE,
            "write_enabled": bool(caps.get("write")),
            "verify_enabled": bool(caps.get("verify")),
            "dry_run_enabled": bool(caps.get("dry_run")),
            "idempotent": bool(caps.get("idempotent")),
            "reversible": bool(caps.get("reversible")),
            "requires_human_approval": bool(caps.get("requires_human_approval")),
            "maturity": maturity,
        },
    )
    return existing
