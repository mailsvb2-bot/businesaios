"""Simulation boot. No-op until simulation routes are wired."""

from __future__ import annotations

from runtime.boot.route_surface import attach_route_surface
from runtime.handlers.simulation_build import handle_simulation_build
from runtime.handlers.simulation_explain import handle_simulation_explain

CANON_BOOT_WIRING_ONLY = True


def register_simulation_routes(app: object) -> object:
    handlers = {
        "simulation_build": handle_simulation_build,
        "simulation_explain": handle_simulation_explain,
    }
    return attach_route_surface(
        app,
        domain="simulation",
        handlers=handlers,
        services={"surface_status": "wired"},
    )
