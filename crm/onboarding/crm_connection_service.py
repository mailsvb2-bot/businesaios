from __future__ import annotations

from crm.onboarding.crm_connection_flow import CrmConnectionFlow
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload, CrmOAuthStartRequest


class CrmConnectionService:
    def __init__(self, flow: CrmConnectionFlow) -> None:
        self._flow = flow

    def begin_oauth(self, request: CrmOAuthStartRequest) -> str:
        return self._flow.start(request)

    def finalize_oauth(self, callback: CrmOAuthCallbackPayload, *, connector, secret_ref: str, external_account_id: str | None = None):
        return self._flow.complete(callback, connector=connector, secret_ref=secret_ref, external_account_id=external_account_id)
