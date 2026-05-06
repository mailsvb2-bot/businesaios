from __future__ import annotations

from typing import Any


def register_flask_routes(*, app: Any, bundle) -> None:
    @app.get("/settings/messaging-preferences")
    def messaging_preferences_html():
        res = bundle.html()
        return res.body, res.status_code, {"content-type": res.content_type}

    @app.get("/api/settings/messaging-preferences")
    def messaging_preferences_model():
        from flask import request

        res = bundle.model(tenant_id=request.args.get("tenant_id", "default"))
        return res.body, res.status_code

    @app.post("/api/settings/messaging-preferences")
    def messaging_preferences_save():
        from flask import request

        payload = request.get_json(silent=True) or {}
        res = bundle.save(
            tenant_id=request.args.get("tenant_id", "default"),
            payload=payload,
        )
        return res.body, res.status_code

    @app.get("/static/channel_preferences.css")
    def messaging_preferences_css():
        res = bundle.css()
        return res.body, res.status_code, {"content-type": res.content_type}

    @app.get("/static/channel_preferences.js")
    def messaging_preferences_js():
        res = bundle.js()
        return res.body, res.status_code, {"content-type": res.content_type}
