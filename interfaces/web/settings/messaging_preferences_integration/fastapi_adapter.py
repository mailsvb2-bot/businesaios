from __future__ import annotations

from typing import Any


def register_fastapi_routes(*, app: Any, bundle) -> None:
    @app.get("/settings/messaging-preferences")
    def messaging_preferences_html():
        from fastapi.responses import HTMLResponse

        res = bundle.html()
        return HTMLResponse(content=res.body, status_code=res.status_code)

    @app.get("/api/settings/messaging-preferences")
    def messaging_preferences_model(tenant_id: str = "default"):
        res = bundle.model(tenant_id=tenant_id)
        return res.body

    @app.post("/api/settings/messaging-preferences")
    def messaging_preferences_save(payload: dict, tenant_id: str = "default"):
        res = bundle.save(tenant_id=tenant_id, payload=payload)
        return res.body

    @app.get("/static/channel_preferences.css")
    def messaging_preferences_css():
        from fastapi.responses import Response

        res = bundle.css()
        return Response(content=res.body, status_code=res.status_code, media_type="text/css")

    @app.get("/static/channel_preferences.js")
    def messaging_preferences_js():
        from fastapi.responses import Response

        res = bundle.js()
        return Response(content=res.body, status_code=res.status_code, media_type="application/javascript")
