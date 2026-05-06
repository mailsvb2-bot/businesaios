from crm.pipeline.crm_pipeline_model_builder import CrmPipelineModelBuilder
from crm.pipeline.crm_pipeline_verifier import CrmPipelineVerifier


def test_pipeline_verifier_accepts_valid_pipeline():
    assert CrmPipelineVerifier().verify_expected_shape(CrmPipelineModelBuilder().build_default()) is True
