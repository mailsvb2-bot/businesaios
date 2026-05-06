"""Governance boot. No-op until governance routes/services are registered."""

from __future__ import annotations

from bootstrap.route_surface import attach_route_surface
from runtime.handlers.governance_build import handle_governance_build
from runtime.handlers.governance_evaluate import handle_governance_evaluate
from runtime.handlers.governance_explain import handle_governance_explain

CANON_BOOT_WIRING_ONLY = True


def register_governance_routes(app: object) -> object:
    handlers = {
        "governance_build": handle_governance_build,
        "governance_explain": handle_governance_explain,
        "governance_evaluate": handle_governance_evaluate,
    }
    return attach_route_surface(
        app,
        domain="governance",
        handlers=handlers,
        services={"surface_status": "wired"},
    )
