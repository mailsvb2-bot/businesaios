from __future__ import annotations

from fastapi.routing import APIRoute

from interfaces.api.fastapi_router_adapter import create_api_router


def test_create_api_router_registers_queue_ops_control_plane_routes() -> None:
    router = create_api_router(application_service=object())
    route_map = {(route.path, tuple(sorted(route.methods or []))) for route in router.routes if isinstance(route, APIRoute)}
    assert ('/control-plane/queue/{tenant_id}/{queue_name}', ('GET',)) in route_map
    assert ('/control-plane/queue/{tenant_id}/{queue_name}/remediation-audit', ('GET',)) in route_map
    assert ('/control-plane/queue/{tenant_id}/{queue_name}/remediation/{hook_code}', ('POST',)) in route_map
