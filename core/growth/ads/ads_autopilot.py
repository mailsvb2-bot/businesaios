from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.ads.ads_service import AdsService
from core.growth.ads.creative import CreativePipeline, CreativePipelineConfig
from core.llm.agent import LLMAgent, LLMTaskContext, TaskType

Json = Dict[str, Any]


@dataclass(frozen=True)
class AdsAutopilot:
    """Single, canonical Ads autopilot entrypoint.

    DecisionCore/executors should use this wrapper instead of calling growth
    submodules directly.
    """

    llm: LLMAgent
    ads: AdsService

    def build_pipeline(self) -> CreativePipeline:
        return CreativePipeline(self.llm, self.ads, CreativePipelineConfig())

    def next_actions(self, ctx: LLMTaskContext) -> Json:
        summary = self.llm.run_task(TaskType.ADS_ANALYTICS_SUMMARY, ctx)
        pipeline = self.build_pipeline()
        plan = pipeline.build_ads_plan(ctx)
        return {
            "analytics": {"text": summary.text, "data": summary.json, "meta": summary.meta},
            "plan": {"commands": [c.__dict__ for c in plan.commands], "notes": plan.notes},
        }
