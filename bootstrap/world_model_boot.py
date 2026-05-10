"""World-model boot. Boot owns wiring only; runtime handlers are late-bound."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from bootstrap.route_surface import attach_route_surface

CANON_WORLD_MODEL_BOOT_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


def _load_handler(module_name: str, attr_name: str) -> Any:
    module = import_module(module_name)
    return getattr(module, attr_name)


def _world_model_handlers() -> dict[str, Any]:
    return {
        "world_model_build": _load_handler("runtime.handlers.world_model_build", "handle_world_model_build"),
        "world_model_explain": _load_handler("runtime.handlers.world_model_explain", "handle_world_model_explain"),
        "world_snapshot_build": _load_handler("runtime.handlers.world_snapshot_build", "handle_world_snapshot_build"),
        "world_snapshot_explain": _load_handler("runtime.handlers.world_snapshot_explain", "handle_world_snapshot_explain"),
    }


def register_world_model_routes(app: object) -> object:
    return attach_route_surface(
        app,
        domain="world_model",
        handlers=_world_model_handlers(),
        services={"surface_status": "wired"},
    )
