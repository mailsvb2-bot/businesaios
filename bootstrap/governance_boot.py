"""Governance boot. Boot owns wiring only; runtime handlers are late-bound."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from bootstrap.route_surface import attach_route_surface

CANON_BOOT_WIRING_ONLY = True


def _load_handler(module_name: str, attr_name: str) -> Any:
    module = import_module(module_name)
    return getattr(module, attr_name)


def _governance_handlers() -> dict[str, Any]:
    return {
        "governance_build": _load_handler("runtime.handlers.governance_build", "handle_governance_build"),
        "governance_explain": _load_handler("runtime.handlers.governance_explain", "handle_governance_explain"),
        "governance_evaluate": _load_handler("runtime.handlers.governance_evaluate", "handle_governance_evaluate"),
    }


def register_governance_routes(app: object) -> object:
    return attach_route_surface(
        app,
        domain="governance",
        handlers=_governance_handlers(),
        services={"surface_status": "wired"},
    )
