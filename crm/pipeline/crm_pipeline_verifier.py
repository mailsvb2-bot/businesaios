from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_pipeline_contract import CrmPipeline


class CrmPipelineVerifier:
    def verify_expected_shape(self, pipeline: CrmPipeline) -> bool:
        if not (pipeline.pipeline_key and pipeline.display_name and pipeline.stages):
            return False
        seen: set[str] = set()
        for stage in pipeline.stages:
            if not stage.stage_key or stage.stage_key in seen:
                return False
            seen.add(stage.stage_key)
        return True

    def verify_remote_shape(self, connector: CrmConnector, connection: CrmConnectionRef, pipeline: CrmPipeline) -> dict[str, object]:
        pipelines = connector.list_pipelines(connection)
        remote = next((item for item in pipelines if item.pipeline_key == pipeline.pipeline_key), None)
        if remote is None:
            return {'verified': False, 'reason': 'pipeline_not_found'}
        if remote.display_name != pipeline.display_name:
            return {'verified': False, 'reason': 'display_name_mismatch'}
        remote_stage_keys = tuple(stage.stage_key for stage in remote.stages)
        expected_stage_keys = tuple(stage.stage_key for stage in pipeline.stages)
        if remote_stage_keys != expected_stage_keys:
            return {
                'verified': False,
                'reason': 'stage_shape_mismatch',
                'expected_stage_keys': expected_stage_keys,
                'actual_stage_keys': remote_stage_keys,
            }
        return {'verified': True, 'reason': 'pipeline_readback_match', 'stage_count': len(remote.stages)}
