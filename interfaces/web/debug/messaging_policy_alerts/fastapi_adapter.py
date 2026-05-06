from __future__ import annotations

from typing import Any


def register_fastapi_routes(*, app: Any, bundle) -> None:
    @app.get("/api/debug/messaging-policy-alerts")
    def debug_messaging_policy_alerts_json(tenant_id: str = "default", user_id: str = "", date_from: str = "", date_to: str = "", limit: int = 500):
        res = bundle.json(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        return res.body

    @app.get("/debug/messaging-policy-alerts")
    def debug_messaging_policy_alerts_html(tenant_id: str = "default", user_id: str = "", date_from: str = "", date_to: str = "", limit: int = 500):
        res = bundle.html(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=res.body, status_code=res.status_code)
