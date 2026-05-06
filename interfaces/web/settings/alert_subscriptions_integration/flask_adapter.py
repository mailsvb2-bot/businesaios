from __future__ import annotations

from typing import Any


def register_flask_routes(*, app: Any, bundle) -> None:
    @app.get("/settings/alert-subscriptions")
    def alert_subscriptions_html():
        res = bundle.html()
        return res.body, res.status_code, {"content-type": res.content_type}

    @app.get("/api/settings/alert-subscriptions")
    def alert_subscriptions_model():
        from flask import request

        res = bundle.model(tenant_id=request.args.get("tenant_id", "default"))
        return res.body, res.status_code

    @app.post("/api/settings/alert-subscriptions")
    def alert_subscriptions_save():
        from flask import request

        res = bundle.save(tenant_id=request.args.get("tenant_id", "default"), payload=request.get_json(silent=True) or {})
        return res.body, res.status_code

    @app.get("/static/alert_subscriptions.css")
    def alert_subscriptions_css():
        res = bundle.css()
        return res.body, res.status_code, {"content-type": res.content_type}

    @app.get("/static/alert_subscriptions.js")
    def alert_subscriptions_js():
        res = bundle.js()
        return res.body, res.status_code, {"content-type": res.content_type}
