from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.state.crm_state_snapshot import CrmStateSnapshot


class CrmStateFeed:
    def fetch(self, connector: CrmConnector, connection: CrmConnectionRef) -> CrmStateSnapshot:
        snapshot = connector.build_snapshot(connection)
        return CrmStateSnapshot(
            tenant_id=connection.tenant_id,
            business_id=connection.business_id,
            provider_key=connection.provider_key,
            open_deals=int(snapshot.get('open_deals', 0)),
            won_deals_last_30d=int(snapshot.get('won_deals_last_30d', 0)),
            lost_deals_last_30d=int(snapshot.get('lost_deals_last_30d', 0)),
            stalled_deals=int(snapshot.get('stalled_deals', 0)),
            metadata={
                'pipeline_count': int(snapshot.get('pipeline_count', 0)),
                'contact_count': int(snapshot.get('contact_count', 0)),
                'deal_count': int(snapshot.get('deal_count', 0)),
                'recent_activity': tuple(snapshot.get('recent_activity', ())),
            },
        )
