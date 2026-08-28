from __future__ import annotations

import asyncio

import pytest
from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from adapters.api.fastapi.provider_webhook_routes import register_provider_webhook_routes


class _ProviderAdminHandlers:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.payload: dict | None = None

    def ingest_provider_webhook(self, *, payload: dict) -> dict:
        self.payload = payload
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

    return Request(
        {
            'type': 'http',
            'method': 'POST',
            'path': '/providers/webhook/tenant-a/business-a/slack_messaging',
            'query_string': b'',
            'headers': [(b'content-type', b'application/json')],
        },
        receive,
    )


def test_slack_url_verification_returns_plain_challenge_after_accepted_ingest() -> None:
    handler = _ProviderAdminHandlers(
        {'status': 'accepted', 'metadata': {}, 'transport_ack_safe': True}
    )
    body = b'{"type":"url_verification","event_id":"Ev-verify","challenge":"challenge-token"}'

    response = asyncio.run(
        _endpoint(handler)(
            'tenant-a',
            'business-a',
            'slack_messaging',
            _request(body),
        )
    )

    assert response.body == b'challenge-token'
    assert response.media_type == 'text/plain'
    assert handler.payload is not None
    assert handler.payload['event_key'] == 'Ev-verify'
    assert handler.payload['topic'] == 'url_verification'
    assert handler.payload['body'] == body.decode()


def test_slack_invalid_signature_is_denied_before_url_verification_ack() -> None:
    handler = _ProviderAdminHandlers(
        {'status': 'invalid_signature', 'metadata': {}, 'transport_ack_safe': False}
    )
    body = b'{"type":"url_verification","event_id":"Ev-bad","challenge":"must-not-ack"}'

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            _endpoint(handler)(
                'tenant-a',
                'business-a',
                'slack_messaging',
                _request(body),
            )
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == 'provider_webhook_signature_denied'
