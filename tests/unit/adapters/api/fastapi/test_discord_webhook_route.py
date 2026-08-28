from __future__ import annotations

import asyncio

import pytest
from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from adapters.api.fastapi.provider_webhook_routes import register_provider_webhook_routes


class _ProviderAdminHandlers:
    def __init__(self, result: dict) -> None:
        self.result = result
    def ingest_provider_webhook(self, *, payload: dict) -> dict:
        return dict(self.result)


def _endpoint(handler: _ProviderAdminHandlers):
    router = APIRouter()
    register_provider_webhook_routes(router=router, provider_admin_handlers=handler)
    return next(route.endpoint for route in router.routes if route.path == '/providers/webhook/{tenant_id}/{business_id}/{provider_key}')


def _request(body: bytes) -> Request:
    sent = False
    async def receive() -> dict:
        nonlocal sent
        if sent:
            return {'type': 'http.disconnect'}
        sent = True
        return {'type': 'http.request', 'body': body, 'more_body': False}
    return Request({'type': 'http', 'method': 'POST', 'path': '/providers/webhook/tenant-a/business-a/discord_messaging', 'query_string': b'', 'headers': [(b'content-type', b'application/json')]}, receive)


@pytest.mark.parametrize(('body', 'expected_status', 'expected_body'), [(b'{"type":0}', 204, b''), (b'{"type":1}', 200, b'{"type":1}'), (b'{"type":1,"event":{"type":"MESSAGE_CREATE","data":{}}}', 204, b'')])
def test_discord_ping_is_acknowledged_only_after_accepted_ingest(body: bytes, expected_status: int, expected_body: bytes) -> None:
    handler = _ProviderAdminHandlers({'status': 'accepted', 'metadata': {}, 'transport_ack_safe': True})
    response = asyncio.run(_endpoint(handler)('tenant-a', 'business-a', 'discord_messaging', _request(body)))
    assert response.status_code == expected_status
    assert response.body == expected_body


def test_discord_invalid_signature_uses_vendor_required_401() -> None:
    handler = _ProviderAdminHandlers({'status': 'invalid_signature', 'metadata': {}, 'transport_ack_safe': False})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_endpoint(handler)('tenant-a', 'business-a', 'discord_messaging', _request(b'{"type":1}')))
    assert exc.value.status_code == 401
    assert exc.value.detail == 'provider_webhook_signature_denied'
