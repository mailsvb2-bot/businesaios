from __future__ import annotations

from importlib import import_module
from typing import Any

from contracts.event_store import EventStore

from bootstrap.knowledge_bundle import KnowledgeRuntimeBundle
from bootstrap.route_surface import attach_route_surface
from bootstrap.knowledge_wiring import build_knowledge_runtime_bundle

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_KNOWLEDGE_BOOT_FINAL_OWNER = True


def _load_handler(module_name: str, attr_name: str) -> Any:
    module = import_module(module_name)
    return getattr(module, attr_name)


def build_knowledge_services(*, event_store: EventStore, tenant_id: str) -> KnowledgeRuntimeBundle:
    return build_knowledge_runtime_bundle(event_store=event_store, tenant_id=tenant_id)


def _knowledge_handlers() -> dict[str, Any]:
    return {
        "knowledge_build": _load_handler("runtime.handlers.knowledge_build", "handle_knowledge_build"),
        "knowledge_explain": _load_handler("runtime.handlers.knowledge_explain", "handle_knowledge_explain"),
    }


def register_knowledge_routes(app: object) -> object:
    return attach_route_surface(
        app,
        domain="knowledge",
        handlers=_knowledge_handlers(),
        services={
            "build_knowledge_services": build_knowledge_services,
            "surface_status": "wired",
        },
    )
