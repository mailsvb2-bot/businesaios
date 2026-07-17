"""Execution adapter for the signed demand-route advisory action."""

from __future__ import annotations

from typing import Any

CANON_DEMAND_ROUTE_HANDLER = True


def handle_route_lead(payload, effects, env) -> dict[str, Any]:
    """Return the already-decided route without choosing or mutating anything."""

    body = dict(payload or {})
    return {
        "status": "advisory",
        "decision_id": str(env.decision.decision_id),
        "correlation_id": str(env.decision.correlation_id),
        "route": body,
    }


__all__ = ["CANON_DEMAND_ROUTE_HANDLER", "handle_route_lead"]
