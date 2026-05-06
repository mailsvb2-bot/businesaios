"""Economics boot. No-op until economics HTTP/API surface is wired."""

from __future__ import annotations

from runtime.boot.route_surface import attach_route_surface
from runtime.handlers.economics_build import handle_economics_build
from runtime.handlers.economics_explain import handle_economics_explain
from runtime.handlers.economics_score_candidates import handle_economics_score_candidates

CANON_BOOT_WIRING_ONLY = True


def register_economics_routes(app: object) -> object:
    handlers = {
        "economics_build": handle_economics_build,
        "economics_explain": handle_economics_explain,
        "economics_score_candidates": handle_economics_score_candidates,
    }
    return attach_route_surface(
        app,
        domain="economics",
        handlers=handlers,
        services={"surface_status": "wired"},
    )
