from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector


class CrmPipelineSyncService:
    def sync(self, connector: CrmConnector, connection: CrmConnectionRef) -> dict[str, object]:
        return {'pipelines': [pipeline.pipeline_key for pipeline in connector.list_pipelines(connection)]}
