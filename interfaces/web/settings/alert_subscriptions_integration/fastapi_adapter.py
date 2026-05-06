from __future__ import annotations

from typing import Any


def register_fastapi_routes(*, app: Any, bundle) -> None:
    @app.get("/settings/alert-subscriptions")
    def alert_subscriptions_html():
        from fastapi.responses import HTMLResponse

        res = bundle.html()
        return HTMLResponse(content=res.body, status_code=res.status_code)

    @app.get("/api/settings/alert-subscriptions")
    def alert_subscriptions_model(tenant_id: str = "default"):
        res = bundle.model(tenant_id=tenant_id)
        return res.body

    @app.post("/api/settings/alert-subscriptions")
    def alert_subscriptions_save(payload: dict, tenant_id: str = "default"):
        res = bundle.save(tenant_id=tenant_id, payload=payload)
        return res.body

    @app.get("/static/alert_subscriptions.css")
    def alert_subscriptions_css():
        from fastapi.responses import Response

        res = bundle.css()
        return Response(content=res.body, status_code=res.status_code, media_type="text/css")

    @app.get("/static/alert_subscriptions.js")
    def alert_subscriptions_js():
        from fastapi.responses import Response

        res = bundle.js()
        return Response(content=res.body, status_code=res.status_code, media_type="application/javascript")
