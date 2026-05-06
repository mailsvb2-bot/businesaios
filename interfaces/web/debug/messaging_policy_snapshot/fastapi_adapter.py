from __future__ import annotations

from typing import Any


def register_fastapi_routes(*, app: Any, bundle) -> None:
    @app.get('/api/debug/messaging-policy-snapshot')
    def debug_messaging_policy_snapshot_json(tenant_id: str = 'default', user_id: str = '', correlation_id: str = ''):
        res = bundle.json(tenant_id=tenant_id, user_id=user_id, correlation_id=correlation_id)
        return res.body

    @app.get('/debug/messaging-policy-snapshot')
    def debug_messaging_policy_snapshot_html(tenant_id: str = 'default', user_id: str = '', correlation_id: str = ''):
        res = bundle.html(tenant_id=tenant_id, user_id=user_id, correlation_id=correlation_id)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=res.body, status_code=res.status_code)
