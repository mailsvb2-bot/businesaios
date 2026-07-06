from __future__ import annotations

from collections.abc import Callable
from typing import Any

from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_service_graph
from runtime.boot.web.runtime_web_service_builders import build_messaging_policy_dashboard_bundle

CANON_BOOT_WIRING_ONLY = True

def boot_messaging_policy_dashboard(*, app: Any, event_store: Any, route_registrar: Callable[..., None]) -> None:
    graph = build_messaging_policy_service_graph(event_store=event_store)
    bundle = build_messaging_policy_dashboard_bundle(trace_search_service=graph.trace_search_service)
    route_registrar(app=app, bundle=bundle)
