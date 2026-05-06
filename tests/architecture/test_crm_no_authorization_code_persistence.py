from crm.onboarding.crm_connection_flow import CrmConnectionFlow
from crm.onboarding.crm_connection_verifier import CrmConnectionVerifier
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload, CrmOAuthStartRequest
from crm.onboarding.crm_oauth_state_store import InMemoryCrmOAuthStateStore


class _Connector:
    def __init__(self) -> None:
        self.provider = type("Provider", (), {"provider_key": "hubspot"})()

    def supports_live_api(self) -> bool:
        return False

    def verify_connection(self, connection):
        return {"verified": True}


def test_connection_metadata_does_not_persist_authorization_code() -> None:
    state_store = InMemoryCrmOAuthStateStore()
    flow = CrmConnectionFlow(state_store=state_store, verifier=CrmConnectionVerifier())
    state_store.save(CrmOAuthStartRequest(tenant_id="t1", business_id="b1", provider_key="hubspot", redirect_uri="https://app/callback", state_token="state-1"))

    result = flow.complete(
        CrmOAuthCallbackPayload(
            provider_key="hubspot",
            state_token="state-1",
            authorization_code="top-secret-code",
            metadata={"authorization_code": "top-secret-code", "portal_id": "123"},
        ),
        connector=_Connector(),
        secret_ref="secret-1",
    )

    assert result.connection is not None
    assert "authorization_code" not in result.connection.metadata
