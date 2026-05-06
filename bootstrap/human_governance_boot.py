"""Human-governance boot. No-op until human-governance runtime is wired."""

from __future__ import annotations

from bootstrap.route_surface import attach_route_surface
from runtime.handlers.human_governance_build import handle_human_governance_build
from runtime.handlers.human_governance_explain import handle_human_governance_explain

CANON_BOOT_WIRING_ONLY = True


def register_human_governance_routes(app: object) -> object:
    handlers = {
        "human_governance_build": handle_human_governance_build,
        "human_governance_explain": handle_human_governance_explain,
    }
    return attach_route_surface(
        app,
        domain="human_governance",
        handlers=handlers,
        services={"surface_status": "wired"},
    )
