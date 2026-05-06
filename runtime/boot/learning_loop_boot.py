"""Learning-loop boot. No-op until learning-loop contour is wired."""

from __future__ import annotations

from runtime.boot.route_surface import attach_route_surface
from runtime.handlers.learning_loop_build import handle_learning_loop_build
from runtime.handlers.learning_loop_explain import handle_learning_loop_explain

CANON_BOOT_WIRING_ONLY = True


def register_learning_loop_routes(app: object) -> object:
    handlers = {
        "learning_loop_build": handle_learning_loop_build,
        "learning_loop_explain": handle_learning_loop_explain,
    }
    return attach_route_surface(
        app,
        domain="learning_loop",
        handlers=handlers,
        services={"surface_status": "wired", "learning_loop_run_surface": "available_via_runtime.handlers.learning_loop_run"},
    )
