from __future__ import annotations

from crm.onboarding.crm_connection_service import CrmConnectionService
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload


class CrmOAuthCallbackHandler:
    def __init__(self, service: CrmConnectionService) -> None:
        self._service = service

    def handle(self, payload: CrmOAuthCallbackPayload, *, connector, secret_ref: str, external_account_id: str | None = None):
        return self._service.finalize_oauth(payload, connector=connector, secret_ref=secret_ref, external_account_id=external_account_id)
