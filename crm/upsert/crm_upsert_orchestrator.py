from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_verification_contract import CrmVerificationRequest
from crm.upsert.crm_contact_upsert_service import CrmContactUpsertService
from crm.upsert.crm_deal_upsert_service import CrmDealUpsertService
from crm.upsert.crm_idempotency_policy import CrmIdempotencyPolicy
from crm.upsert.crm_upsert_result import CrmUpsertResult


class CrmUpsertOrchestrator:
    def __init__(self, *, contact_service: CrmContactUpsertService | None = None, deal_service: CrmDealUpsertService | None = None, idempotency_policy: CrmIdempotencyPolicy | None = None) -> None:
        self._contact_service = contact_service or CrmContactUpsertService()
        self._deal_service = deal_service or CrmDealUpsertService()
        self._idempotency_policy = idempotency_policy or CrmIdempotencyPolicy()

    def upsert_contact(self, connector: CrmConnector, connection: CrmConnectionRef, contact, *, idempotency_key: str) -> CrmUpsertResult:
        stable = self._idempotency_policy.ensure(idempotency_key)
        payload = self._contact_service.upsert(connector, connection, contact, idempotency_key=stable)
        verification = connector.verify_write(connection, CrmVerificationRequest(entity_type='contact', provider_key=connection.provider_key, record_id=str(payload.get('record_id')), expected_fields={'email': contact.identity.email}))
        return CrmUpsertResult(entity_type='contact', operation=str(payload.get('operation', 'upsert')), record_id=str(payload.get('record_id')), verified=verification.verified, reason=verification.reason, metadata=payload)

    def upsert_deal(self, connector: CrmConnector, connection: CrmConnectionRef, deal, *, idempotency_key: str) -> CrmUpsertResult:
        stable = self._idempotency_policy.ensure(idempotency_key)
        payload = self._deal_service.upsert(connector, connection, deal, idempotency_key=stable)
        verification = connector.verify_write(connection, CrmVerificationRequest(entity_type='deal', provider_key=connection.provider_key, record_id=str(payload.get('record_id')), expected_fields={'stage_key': deal.stage_key}))
        return CrmUpsertResult(entity_type='deal', operation=str(payload.get('operation', 'upsert')), record_id=str(payload.get('record_id')), verified=verification.verified, reason=verification.reason, metadata=payload)
