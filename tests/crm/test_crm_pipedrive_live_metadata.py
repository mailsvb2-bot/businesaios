from crm.onboarding.crm_connection_flow import CrmConnectionFlow
from crm.onboarding.crm_connection_verifier import CrmConnectionVerifier
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload, CrmOAuthStartRequest
from crm.onboarding.crm_oauth_state_store import InMemoryCrmOAuthStateStore


class _Connector:
    def __init__(self) -> None:
        self.provider = type("Provider", (), {"provider_key": "pipedrive"})()

    def supports_live_api(self) -> bool:
        return True

    def exchange_oauth_code(self, *, secret_ref: str, authorization_code: str, redirect_uri: str) -> None:
        return None

    def verify_connection(self, connection):
        return {"verified": bool(connection.metadata.get("company_domain")), "reason": "verified"}


def test_complete_preserves_pipedrive_company_domain() -> None:
    state_store = InMemoryCrmOAuthStateStore()
    flow = CrmConnectionFlow(state_store=state_store, verifier=CrmConnectionVerifier())
    state_store.save(CrmOAuthStartRequest(tenant_id="t1", business_id="b1", provider_key="pipedrive", redirect_uri="https://app/callback", state_token="state-1"))

    result = flow.complete(
        CrmOAuthCallbackPayload(
            provider_key="pipedrive",
            state_token="state-1",
            authorization_code="code-1",
            metadata={"company_domain": "example", "account_id": "acct-1", "authorization_code": "should-not-pass"},
        ),
        connector=_Connector(),
        secret_ref="secret-1",
    )

    assert result.success is True
    assert result.connection is not None
    assert result.connection.metadata["company_domain"] == "example"
    assert result.connection.external_account_id == "acct-1"
    assert "authorization_code" not in result.connection.metadata
