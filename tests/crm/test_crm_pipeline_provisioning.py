from crm.pipeline.crm_pipeline_model_builder import CrmPipelineModelBuilder
from crm.pipeline.crm_pipeline_provision_service import CrmPipelineProvisionService


def test_pipeline_provisioning_reports_success(hubspot_connector, connection):
    pipeline = CrmPipelineModelBuilder().build_default()
    result = CrmPipelineProvisionService().provision(hubspot_connector, connection, pipeline, idempotency_key='k1')
    assert result['provisioned'] is True
