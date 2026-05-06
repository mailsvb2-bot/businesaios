from __future__ import annotations

from crm.crm_pipeline_contract import CrmPipeline


class CrmPipelineStageMapper:
    def stage_key_by_name(self, pipeline: CrmPipeline, display_name: str) -> str | None:
        normalized = display_name.strip().casefold()
        for stage in pipeline.stages:
            if stage.display_name.casefold() == normalized:
                return stage.stage_key
        return None
