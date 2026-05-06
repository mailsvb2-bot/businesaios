from crm.pipeline.crm_pipeline_model_builder import CrmPipelineModelBuilder


def test_pipeline_model_builder_returns_default_pipeline():
    pipeline = CrmPipelineModelBuilder().build_default()
    assert pipeline.pipeline_key == 'default_sales'
    assert len(pipeline.stages) >= 3
