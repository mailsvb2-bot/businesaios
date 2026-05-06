from __future__ import annotations

from contracts.event_store import EventStore

from bootstrap.knowledge_bundle import KnowledgeRuntimeBundle
from bootstrap.route_surface import attach_route_surface
from bootstrap.knowledge_wiring import build_knowledge_runtime_bundle
from runtime.handlers.knowledge_build import handle_knowledge_build
from runtime.handlers.knowledge_explain import handle_knowledge_explain

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_KNOWLEDGE_BOOT_FINAL_OWNER = True


def build_knowledge_services(*, event_store: EventStore, tenant_id: str) -> KnowledgeRuntimeBundle:
    return build_knowledge_runtime_bundle(event_store=event_store, tenant_id=tenant_id)


def register_knowledge_routes(app: object) -> object:
    handlers = {
        "knowledge_build": handle_knowledge_build,
        "knowledge_explain": handle_knowledge_explain,
    }
    return attach_route_surface(
        app,
        domain="knowledge",
        handlers=handlers,
        services={
            "build_knowledge_services": build_knowledge_services,
            "surface_status": "wired",
        },
    )
