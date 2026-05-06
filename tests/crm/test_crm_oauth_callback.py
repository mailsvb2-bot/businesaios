from crm.onboarding.crm_connection_flow import CrmConnectionFlow
from crm.onboarding.crm_connection_service import CrmConnectionService
from crm.onboarding.crm_connection_verifier import CrmConnectionVerifier
from crm.onboarding.crm_oauth_callback_handler import CrmOAuthCallbackHandler
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload, CrmOAuthStartRequest
from crm.onboarding.crm_oauth_state_store import InMemoryCrmOAuthStateStore


def test_oauth_callback_handler_uses_service(hubspot_connector):
    flow = CrmConnectionFlow(state_store=InMemoryCrmOAuthStateStore(), verifier=CrmConnectionVerifier())
    service = CrmConnectionService(flow)
    handler = CrmOAuthCallbackHandler(service)
    service.begin_oauth(CrmOAuthStartRequest(tenant_id='t1', business_id='b1', provider_key='hubspot', redirect_uri='https://x', state_token='s2'))
    result = handler.handle(CrmOAuthCallbackPayload(provider_key='hubspot', state_token='s2', authorization_code='abc'), connector=hubspot_connector, secret_ref='secret://x')
    assert result.success is True
