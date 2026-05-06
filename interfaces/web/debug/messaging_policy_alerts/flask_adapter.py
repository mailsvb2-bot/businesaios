from __future__ import annotations

from typing import Any


def register_flask_routes(*, app: Any, bundle) -> None:
    @app.get("/api/debug/messaging-policy-alerts")
    def debug_messaging_policy_alerts_json():
        from flask import request
        res = bundle.json(
            tenant_id=request.args.get("tenant_id", "default"),
            user_id=request.args.get("user_id", ""),
            date_from=request.args.get("date_from", ""),
            date_to=request.args.get("date_to", ""),
            limit=request.args.get("limit", "500"),
        )
        return res.body, res.status_code

    @app.get("/debug/messaging-policy-alerts")
    def debug_messaging_policy_alerts_html():
        from flask import request
        res = bundle.html(
            tenant_id=request.args.get("tenant_id", "default"),
            user_id=request.args.get("user_id", ""),
            date_from=request.args.get("date_from", ""),
            date_to=request.args.get("date_to", ""),
            limit=request.args.get("limit", "500"),
        )
        return res.body, res.status_code, {"content-type": res.content_type}
