from crm.pipeline.crm_pipeline_model_builder import CrmPipelineModelBuilder
from crm.pipeline.crm_pipeline_provision_service import CrmPipelineProvisionService


def test_pipeline_provisioning_verifies_remote_readback(hubspot_connector, connection):
    pipeline = CrmPipelineModelBuilder().build_default()
    result = CrmPipelineProvisionService().provision(hubspot_connector, connection, pipeline, idempotency_key='pipeline-1')

    assert result['provisioned'] is True
    assert result['verification']['reason'] == 'pipeline_readback_match'
