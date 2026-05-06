from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.onboarding.crm_connection_result import CrmConnectionResult


class CrmConnectionVerifier:
    def verify(
        self,
        connector: CrmConnector,
        connection: CrmConnectionRef,
    ) -> CrmConnectionResult:
        if not connection.secret_ref:
            return CrmConnectionResult(
                success=False,
                connection=None,
                reason='missing_secret_ref',
                diagnostics={'verified': False, 'reason': 'missing_secret_ref'},
            )

        payload = connector.verify_connection(connection)
        verified_provider = getattr(getattr(connector, 'provider', None), 'provider_key', None)
        provider_matches = verified_provider in (None, connection.provider_key)
        ok = bool(payload.get('verified')) and provider_matches
        reason = str(
            payload.get(
                'reason',
                'verified' if ok else 'provider_mismatch' if not provider_matches else 'failed',
            )
        )
        diagnostics = dict(payload)
        diagnostics['provider_matches'] = provider_matches
        diagnostics['provider_key'] = connection.provider_key
        return CrmConnectionResult(
            success=ok,
            connection=connection if ok else None,
            reason=reason,
            diagnostics=diagnostics,
        )
