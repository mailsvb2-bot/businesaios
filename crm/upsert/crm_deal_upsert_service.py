from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_deal_contract import CrmDeal


class CrmDealUpsertService:
    def upsert(self, connector: CrmConnector, connection: CrmConnectionRef, deal: CrmDeal, *, idempotency_key: str) -> dict[str, object]:
        return connector.upsert_deal(connection, deal, idempotency_key=idempotency_key)
