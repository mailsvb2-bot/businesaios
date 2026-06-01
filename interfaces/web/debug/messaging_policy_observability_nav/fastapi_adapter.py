from __future__ import annotations

from typing import Any


def register_fastapi_routes(*, app: Any, bundle) -> None:
    @app.get("/api/debug/messaging-policy-observability")
    def debug_messaging_policy_observability_json(tenant_id: str = "default"):
        return bundle.json(tenant_id=tenant_id).body

    @app.get("/debug/messaging-policy-observability")
    def debug_messaging_policy_observability_html(tenant_id: str = "default"):
        from fastapi.responses import HTMLResponse
        res = bundle.html(tenant_id=tenant_id)
        return HTMLResponse(content=res.body, status_code=res.status_code)
