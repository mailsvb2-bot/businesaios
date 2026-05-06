from __future__ import annotations

from crm.crm_pipeline_contract import CrmPipeline
from crm.crm_stage_contract import CrmStage


class CrmPipelineTemplateCatalog:
    def default_sales_pipeline(self) -> CrmPipeline:
        return CrmPipeline(
            pipeline_key='default_sales',
            display_name='Default Sales Pipeline',
            stages=(
                CrmStage('new', 'New', 10),
                CrmStage('qualified', 'Qualified', 20),
                CrmStage('proposal', 'Proposal', 30),
                CrmStage('won', 'Won', 40, is_closed=True, is_won=True),
                CrmStage('lost', 'Lost', 50, is_closed=True, is_won=False),
            ),
        )
