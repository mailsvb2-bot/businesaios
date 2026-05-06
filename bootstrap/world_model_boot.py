"""World-model boot. No-op until world-model routes/services are wired."""

from __future__ import annotations


from bootstrap.route_surface import attach_route_surface
from runtime.handlers.world_model_build import handle_world_model_build
from runtime.handlers.world_model_explain import handle_world_model_explain
from runtime.handlers.world_snapshot_build import handle_world_snapshot_build
from runtime.handlers.world_snapshot_explain import handle_world_snapshot_explain

CANON_WORLD_MODEL_BOOT_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


def register_world_model_routes(app: object) -> object:
    handlers = {
        "world_model_build": handle_world_model_build,
        "world_model_explain": handle_world_model_explain,
        "world_snapshot_build": handle_world_snapshot_build,
        "world_snapshot_explain": handle_world_snapshot_explain,
    }
    return attach_route_surface(
        app,
        domain="world_model",
        handlers=handlers,
        services={"surface_status": "wired"},
    )
