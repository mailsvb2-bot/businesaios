from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_verification_contract import CrmVerificationRequest, CrmVerificationResult
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.pipedrive.pipedrive_api_config import PipedriveApiConfig
from crm.providers.pipedrive.pipedrive_auth_adapter import PipedriveAuthAdapter


class PipedriveVerificationAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: PipedriveAuthAdapter | None = None, api_config: PipedriveApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or PipedriveApiConfig()

    def verify(self, connection: CrmConnectionRef | None = None, request: CrmVerificationRequest | None = None, *, secret_ref: str | None = None, company_domain: str | None = None) -> CrmVerificationResult:
        assert request is not None
        if self._auth_adapter is None or not secret_ref or not company_domain:
            assert connection is not None and self._store is not None
            record = self._store.get_record(connection, entity_type=request.entity_type, record_id=request.record_id)
        else:
            client = self._auth_adapter.authorized_client(secret_ref=secret_ref, company_domain=company_domain)
            endpoint = {'contact': 'persons', 'deal': 'deals', 'note': 'notes'}.get(request.entity_type)
            if endpoint is None or not request.record_id:
                return CrmVerificationResult(False, 'pipedrive', request.entity_type, request.record_id, 'unsupported_entity_type', {})
            response = client.send(CrmHttpRequest(method='GET', path=f'/{endpoint}/{request.record_id}'))
            payload = response.json_body if isinstance(response.json_body, dict) else {}
            record = payload.get('data') if isinstance(payload.get('data'), dict) else payload
        mismatches = {}
        if record is not None:
            for key, expected in request.expected_fields.items():
                actual = record.get(key)
                if expected is not None and actual != expected:
                    mismatches[key] = {'expected': expected, 'actual': actual}
        verified = record is not None and not mismatches
        reason = 'provider_readback_match' if verified else 'record_not_found' if record is None else 'field_mismatch'
        return CrmVerificationResult(verified=verified, provider_key='pipedrive', entity_type=request.entity_type, record_id=request.record_id, reason=reason, evidence={'record': record or {}, 'mismatches': mismatches})
