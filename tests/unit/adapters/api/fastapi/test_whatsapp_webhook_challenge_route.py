from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi import public_routes
from application.business_autonomy.provider_catalog import provider_map
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _vault() -> InMemorySecretVault:
    provider = provider_map()['whatsapp_cloud']
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a', secret_name=f'{provider.connector_id}.verify_token')
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=b'verify-me')
    return vault


def _endpoint(monkeypatch):
    monkeypatch.setattr(public_routes, 'register_public_core_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_public_site_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_public_client_outcome_routes', lambda **_: None)
    router = APIRouter()
    public_routes.register_public_api_routes(router=router, dependency_container=SimpleNamespace(secret_vault=_vault()), health_handler=None, handlers=None, headless_handlers=None, governance_handlers=None, business_memory_handlers=None, governance_advanced_handlers=None, security_guard=object())
    return next(route.endpoint for route in router.routes if route.path.endswith('/whatsapp_cloud'))


def _request(token: str) -> Request:
    query = f'hub.mode=subscribe&hub.verify_token={token}&hub.challenge=12345'.encode()
    return Request({'type': 'http', 'method': 'GET', 'path': '/providers/webhook/tenant-a/business-a/whatsapp_cloud', 'query_string': query, 'headers': []})


def test_whatsapp_http_challenge_returns_raw_text_plain(monkeypatch) -> None:
    response = asyncio.run(_endpoint(monkeypatch)('tenant-a', 'business-a', _request('verify-me')))
    assert response.body == b'12345'
    assert response.media_type == 'text/plain'


def test_whatsapp_http_challenge_fails_closed_on_token_mismatch(monkeypatch) -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_endpoint(monkeypatch)('tenant-a', 'business-a', _request('wrong')))
    assert exc.value.status_code == 403
