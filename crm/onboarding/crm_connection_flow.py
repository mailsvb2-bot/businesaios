from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.onboarding.crm_connection_result import CrmConnectionResult
from crm.onboarding.crm_provider_connection_metadata import extract_provider_connection_metadata
from crm.onboarding.crm_connection_state_machine import CrmConnectionStateMachine
from crm.onboarding.crm_connection_verifier import CrmConnectionVerifier
from crm.onboarding.crm_credential_binding import CrmCredentialBinding
from crm.onboarding.crm_oauth_contract import (
    CrmOAuthCallbackPayload,
    CrmOAuthStartRequest,
)
from crm.onboarding.crm_oauth_state_store import InMemoryCrmOAuthStateStore
from security.integrations.crm_audit_redaction_policy import CrmAuditRedactionPolicy
from security.integrations.crm_secret_binding import CrmSecretBinding
from security.integrations.crm_token_binding_policy import CrmTokenBindingPolicy


class CrmConnectionFlow:
    def __init__(
        self,
        *,
        state_store: InMemoryCrmOAuthStateStore,
        verifier: CrmConnectionVerifier,
        state_machine: CrmConnectionStateMachine | None = None,
        audit_redaction_policy: CrmAuditRedactionPolicy | None = None,
    ) -> None:
        self._state_store = state_store
        self._verifier = verifier
        self._state_machine = state_machine or CrmConnectionStateMachine()
        self._audit_redaction_policy = audit_redaction_policy or CrmAuditRedactionPolicy()
        self._secret_binding = CrmSecretBinding()
        self._token_binding_policy = CrmTokenBindingPolicy()

    def start(self, request: CrmOAuthStartRequest) -> str:
        self._state_store.save(request)
        return self._state_machine.transition('pending', 'oauth_started')

    def complete(
        self,
        callback: CrmOAuthCallbackPayload,
        *,
        connector,
        secret_ref: str,
        external_account_id: str | None = None,
    ) -> CrmConnectionResult:
        start_request = self._state_store.pop(callback.state_token)
        self._state_machine.transition('oauth_started', 'authorized')
        live_api = self._exchange_live_oauth_if_supported(
            connector=connector,
            secret_ref=secret_ref,
            authorization_code=callback.authorization_code,
            redirect_uri=start_request.redirect_uri,
        )

        credential_binding = CrmCredentialBinding(
            secret_ref=secret_ref,
            token_binding_ref=f"{start_request.provider_key}:token:{start_request.tenant_id}:{start_request.business_id}",
            provider_key=start_request.provider_key,
        )
        provider_metadata = extract_provider_connection_metadata(
            provider_key=start_request.provider_key,
            metadata=callback.metadata,
        )
        redacted_metadata = self._audit_redaction_policy.redact(
            {
                'secret_binding': self._secret_binding.bind(
                    provider_key=start_request.provider_key,
                    secret_ref=credential_binding.secret_ref,
                ),
                'token_binding': self._token_binding_policy.bind(
                    provider_key=start_request.provider_key,
                    token_ref=credential_binding.token_binding_ref,
                ),
                'oauth_state_token': callback.state_token,
                'live_api': live_api,
                **provider_metadata,
            }
        )

        resolved_external_account_id = external_account_id or str(callback.metadata.get('account_id') or '').strip() or None

        connection = CrmConnectionRef(
            tenant_id=start_request.tenant_id,
            business_id=start_request.business_id,
            provider_key=start_request.provider_key,
            connection_id=(
                f"{start_request.provider_key}:{start_request.tenant_id}:{start_request.business_id}"
            ),
            status='authorized',
            secret_ref=secret_ref,
            external_account_id=resolved_external_account_id,
            metadata=redacted_metadata,
        )
        return self._verifier.verify(connector, connection)

    @staticmethod
    def _exchange_live_oauth_if_supported(
        *,
        connector,
        secret_ref: str,
        authorization_code: str,
        redirect_uri: str,
    ) -> bool:
        supports_live = bool(getattr(connector, 'supports_live_api', lambda: False)())
        if not supports_live:
            return False
        exchange = getattr(connector, 'exchange_oauth_code', None)
        if exchange is None:
            raise RuntimeError('Connector claims live API support but does not expose exchange_oauth_code')
        exchange(
            secret_ref=secret_ref,
            authorization_code=authorization_code,
            redirect_uri=redirect_uri,
        )
        return True
