"""Human-governance boot. Boot owns wiring only; runtime handlers are late-bound."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from bootstrap.route_surface import attach_route_surface

CANON_BOOT_WIRING_ONLY = True


def _load_handler(module_name: str, attr_name: str) -> Any:
    module = import_module(module_name)
    return getattr(module, attr_name)


def _human_governance_handlers() -> dict[str, Any]:
    return {
        "human_governance_build": _load_handler("runtime.handlers.human_governance_build", "handle_human_governance_build"),
        "human_governance_explain": _load_handler("runtime.handlers.human_governance_explain", "handle_human_governance_explain"),
    }


def register_human_governance_routes(app: object) -> object:
    return attach_route_surface(
        app,
        domain="human_governance",
        handlers=_human_governance_handlers(),
        services={"surface_status": "wired"},
    )
