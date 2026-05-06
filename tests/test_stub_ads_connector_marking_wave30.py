from __future__ import annotations

import pytest

from interfaces.ads._readonly_demo_connector import ReadOnlyDemoConnector
from interfaces.ads.contracts import CreateOrUpdateRequest, OAuthConnectRequest


@pytest.mark.asyncio
async def test_stub_connector_is_explicit_about_stub_write_mode() -> None:
    connector = ReadOnlyDemoConnector(platform='demo_ads')
    oauth = await connector.connect(
        OAuthConnectRequest(
            tenant_id='t1',
            user_id='u1',
            redirect_uri='https://example.test/cb',
            state='state-1',
        )
    )
    assert 'example.invalid/oauth' in oauth.authorization_url

    response = await connector.create_or_update(
        tenant_id='t1',
        account_id='a1',
        req=CreateOrUpdateRequest(object_type='campaign', payload={'name': 'demo'}),
    )
    assert response.ok is False
    assert response.raw['connector_mode'] == 'stub'
    assert response.raw['production_ready'] is False
    assert response.raw['error'] == 'write_not_supported'
