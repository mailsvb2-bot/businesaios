from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_pipeline_contract import CrmPipeline
from crm.pipeline.crm_pipeline_verifier import CrmPipelineVerifier


class CrmPipelineProvisionService:
    def __init__(self, verifier: CrmPipelineVerifier | None = None) -> None:
        self._verifier = verifier or CrmPipelineVerifier()

    def provision(self, connector: CrmConnector, connection: CrmConnectionRef, pipeline: CrmPipeline, *, idempotency_key: str) -> dict[str, object]:
        descriptor = connector.capabilities()
        if not descriptor.can_write_pipelines:
            raise RuntimeError('CRM provider cannot provision pipelines')
        payload = connector.upsert_pipeline(connection, pipeline, idempotency_key=idempotency_key)
        verification = self._verifier.verify_remote_shape(connector, connection, pipeline)
        return {
            'provisioned': verification['verified'],
            'pipeline_key': pipeline.pipeline_key,
            'record_id': payload.get('record_id'),
            'operation': payload.get('operation'),
            'idempotency_key': idempotency_key,
            'verification': verification,
        }
