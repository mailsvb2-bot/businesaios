from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_contact_contract import CrmContact


class CrmContactUpsertService:
    def upsert(self, connector: CrmConnector, connection: CrmConnectionRef, contact: CrmContact, *, idempotency_key: str) -> dict[str, object]:
        return connector.upsert_contact(connection, contact, idempotency_key=idempotency_key)
