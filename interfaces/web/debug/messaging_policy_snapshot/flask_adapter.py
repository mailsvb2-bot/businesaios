from __future__ import annotations

from typing import Any


def register_flask_routes(*, app: Any, bundle) -> None:
    @app.get('/api/debug/messaging-policy-snapshot')
    def debug_messaging_policy_snapshot_json():
        from flask import request
        res = bundle.json(
            tenant_id=request.args.get('tenant_id', 'default'),
            user_id=request.args.get('user_id', ''),
            correlation_id=request.args.get('correlation_id', ''),
        )
        return res.body, res.status_code

    @app.get('/debug/messaging-policy-snapshot')
    def debug_messaging_policy_snapshot_html():
        from flask import request
        res = bundle.html(
            tenant_id=request.args.get('tenant_id', 'default'),
            user_id=request.args.get('user_id', ''),
            correlation_id=request.args.get('correlation_id', ''),
        )
        return res.body, res.status_code, {'content-type': res.content_type}
