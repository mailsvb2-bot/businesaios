from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_contact_contract import CrmContact
from crm.crm_deal_contract import CrmDeal
from crm.crm_note_contract import CrmNote
from crm.crm_pipeline_contract import CrmPipeline
from crm.crm_provider_contract import CrmProvider
from crm.crm_verification_contract import CrmVerificationRequest, CrmVerificationResult
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore, InMemoryCrmOAuthTokenStore
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.hubspot.hubspot_api_config import HubSpotApiConfig
from crm.providers.hubspot.hubspot_auth_adapter import HubSpotAuthAdapter
from crm.providers.hubspot.hubspot_capability_descriptor import build_hubspot_capability_descriptor
from crm.providers.hubspot.hubspot_connection_adapter import ProviderConnectionAdapter
from crm.providers.hubspot.hubspot_contact_adapter import HubSpotContactAdapter
from crm.providers.hubspot.hubspot_deal_adapter import HubSpotDealAdapter
from crm.providers.hubspot.hubspot_note_adapter import HubSpotNoteAdapter
from crm.providers.hubspot.hubspot_pipeline_adapter import DEFAULT_PIPELINE, HubSpotPipelineAdapter
from crm.providers.hubspot.hubspot_verification_adapter import HubSpotVerificationAdapter


class HubSpotConnector(CrmConnector):
    def __init__(self, *, token_store: CrmOAuthTokenStore | None = None, client_id: str | None = None, client_secret: str | None = None, api_config: HubSpotApiConfig | None = None) -> None:
        self.provider = CrmProvider(provider_key='hubspot', display_name='HubSpot', capability_descriptor=build_hubspot_capability_descriptor())
        self._store = CrmProviderStore('hubspot', default_pipelines=(DEFAULT_PIPELINE,))
        self._api_config = api_config or HubSpotApiConfig()
        self._auth_adapter = None
        if client_id and client_secret:
            self._auth_adapter = HubSpotAuthAdapter(token_store=token_store or InMemoryCrmOAuthTokenStore(), client_id=client_id, client_secret=client_secret, api_config=self._api_config)
        self._connection_adapter = ProviderConnectionAdapter(self._store, auth_adapter=self._auth_adapter, api_config=self._api_config)
        self._pipeline_adapter = HubSpotPipelineAdapter(self._store, auth_adapter=self._auth_adapter, api_config=self._api_config)
        self._contact_adapter = HubSpotContactAdapter(self._store, auth_adapter=self._auth_adapter, api_config=self._api_config)
        self._deal_adapter = HubSpotDealAdapter(self._store, auth_adapter=self._auth_adapter, api_config=self._api_config)
        self._note_adapter = HubSpotNoteAdapter(self._store, auth_adapter=self._auth_adapter, api_config=self._api_config)
        self._verification_adapter = HubSpotVerificationAdapter(self._store, auth_adapter=self._auth_adapter, api_config=self._api_config)

    def capabilities(self):
        return self.provider.capability_descriptor

    def supports_live_api(self) -> bool:
        return self._auth_adapter is not None

    def exchange_oauth_code(self, *, secret_ref: str, authorization_code: str, redirect_uri: str) -> None:
        if self._auth_adapter is None:
            raise RuntimeError(f'{self.provider.provider_key} connector is not configured for live OAuth')
        self._auth_adapter.exchange_code(
            secret_ref=secret_ref,
            authorization_code=authorization_code,
            redirect_uri=redirect_uri,
        )

    def revoke_oauth_binding(self, *, secret_ref: str) -> None:
        if self._auth_adapter is None:
            return
        self._auth_adapter.revoke_binding(secret_ref=secret_ref)

    def _live(self, connection: CrmConnectionRef) -> bool:
        return bool(self._auth_adapter is not None and connection.secret_ref and bool(connection.metadata.get('live_api')))

    def verify_connection(self, connection: CrmConnectionRef) -> dict[str, object]:
        return self._connection_adapter.verify_connection(connection)

    def list_pipelines(self, connection: CrmConnectionRef):
        if self._live(connection):
            return self._pipeline_adapter.list_pipelines(secret_ref=connection.secret_ref)
        return self._pipeline_adapter.list_pipelines(connection)

    def upsert_pipeline(self, connection: CrmConnectionRef, pipeline: CrmPipeline, *, idempotency_key: str) -> dict[str, object]:
        return self._pipeline_adapter.upsert(connection, pipeline, idempotency_key=idempotency_key)

    def upsert_contact(self, connection: CrmConnectionRef, contact: CrmContact, *, idempotency_key: str) -> dict[str, object]:
        if self._live(connection):
            return self._contact_adapter.upsert(contact=contact, secret_ref=connection.secret_ref, idempotency_key=idempotency_key)
        return self._contact_adapter.upsert(connection, contact, idempotency_key=idempotency_key)

    def upsert_deal(self, connection: CrmConnectionRef, deal: CrmDeal, *, idempotency_key: str) -> dict[str, object]:
        if self._live(connection):
            return self._deal_adapter.upsert(deal=deal, secret_ref=connection.secret_ref, idempotency_key=idempotency_key)
        return self._deal_adapter.upsert(connection, deal, idempotency_key=idempotency_key)

    def append_note(self, connection: CrmConnectionRef, note: CrmNote, *, idempotency_key: str) -> dict[str, object]:
        if self._live(connection):
            return self._note_adapter.append(note=note, secret_ref=connection.secret_ref, idempotency_key=idempotency_key)
        return self._note_adapter.append(connection, note, idempotency_key=idempotency_key)

    def verify_write(self, connection: CrmConnectionRef, request: CrmVerificationRequest) -> CrmVerificationResult:
        if self._live(connection):
            return self._verification_adapter.verify(request=request, secret_ref=connection.secret_ref)
        return self._verification_adapter.verify(connection, request)

    def build_snapshot(self, connection: CrmConnectionRef) -> dict[str, object]:
        return self._store.build_snapshot(connection)
