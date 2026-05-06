from __future__ import annotations

from crm.crm_pipeline_contract import CrmPipeline
from crm.pipeline.crm_pipeline_template_catalog import CrmPipelineTemplateCatalog


class CrmPipelineModelBuilder:
    def __init__(self, catalog: CrmPipelineTemplateCatalog | None = None) -> None:
        self._catalog = catalog or CrmPipelineTemplateCatalog()

    def build_default(self) -> CrmPipeline:
        return self._catalog.default_sales_pipeline()
