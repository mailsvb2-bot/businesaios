from __future__ import annotations

from crm.onboarding.crm_connection_flow import CrmConnectionFlow
from crm.onboarding.crm_connection_verifier import CrmConnectionVerifier
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload, CrmOAuthStartRequest
from crm.onboarding.crm_oauth_state_store import InMemoryCrmOAuthStateStore


class _LiveConnector:
    def __init__(self) -> None:
        self.exchanged: list[tuple[str, str, str]] = []

    def supports_live_api(self) -> bool:
        return True

    def exchange_oauth_code(self, *, secret_ref: str, authorization_code: str, redirect_uri: str) -> None:
        self.exchanged.append((secret_ref, authorization_code, redirect_uri))

    def verify_connection(self, connection):
        return {'verified': True, 'provider_key': connection.provider_key, 'reason': 'verified'}


def test_live_oauth_flow_exchanges_code_and_marks_live_api() -> None:
    flow = CrmConnectionFlow(state_store=InMemoryCrmOAuthStateStore(), verifier=CrmConnectionVerifier())
    flow.start(CrmOAuthStartRequest(tenant_id='t1', business_id='b1', provider_key='hubspot', redirect_uri='https://example.com/cb', state_token='state-1'))
    connector = _LiveConnector()

    result = flow.complete(
        CrmOAuthCallbackPayload(provider_key='hubspot', state_token='state-1', authorization_code='code-123'),
        connector=connector,
        secret_ref='secret://hubspot/live',
    )

    assert connector.exchanged == [('secret://hubspot/live', 'code-123', 'https://example.com/cb')]
    assert result.connection.metadata['live_api'] is True
