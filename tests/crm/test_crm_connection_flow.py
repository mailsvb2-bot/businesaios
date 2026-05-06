from crm.onboarding.crm_connection_flow import CrmConnectionFlow
from crm.onboarding.crm_connection_verifier import CrmConnectionVerifier
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload, CrmOAuthStartRequest
from crm.onboarding.crm_oauth_state_store import InMemoryCrmOAuthStateStore


def test_connection_flow_completes_and_verifies(hubspot_connector):
    flow = CrmConnectionFlow(state_store=InMemoryCrmOAuthStateStore(), verifier=CrmConnectionVerifier())
    flow.start(CrmOAuthStartRequest(tenant_id='t1', business_id='b1', provider_key='hubspot', redirect_uri='https://example.com/cb', state_token='s1'))
    result = flow.complete(CrmOAuthCallbackPayload(provider_key='hubspot', state_token='s1', authorization_code='code-1'), connector=hubspot_connector, secret_ref='secret://hubspot')
    assert result.success is True
