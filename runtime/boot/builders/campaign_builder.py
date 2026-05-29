from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""Boot builder: AutopilotCampaignBuilder wiring.

When LLM_ENABLED=1 and the LLM composer is available, the CreativeGenerator
is upgraded to LLMCreativeGenerator — AI generates headline, copy, and
targeting interests instead of a hardcoded template.
"""

import logging
from typing import Any, Optional

from runtime.boot import (
    AdsSpecBuilder,
    AudienceSelector,
    AutopilotCampaignBuilder,
    BidManager,
    BudgetAllocator,
    CampaignBudgetPolicy,
    CampaignFactory,
    CreativeGenerator,
    TrafficStrategyService,
    TrafficToAdsSpec,
)
from runtime.llm import resolve_runtime_llm_settings
from runtime.platform.config.env_flags import env_bool, env_float, env_str

logger = logging.getLogger(__name__)


def build_autopilot_campaign_builder(
    *,
    llm_client: Any | None = None,
) -> AutopilotCampaignBuilder:
    """Build AutopilotCampaignBuilder.

    Args:
        llm_client: Optional LLMClient.  When provided (and LLM_ENABLED=1),
                    creative generation is upgraded to LLMCreativeGenerator
                    which produces AI-generated headline, copy, and targeting
                    interests.  Without it, the deterministic fallback is used.
    """
    llm_enabled = env_bool("LLM_ENABLED") or env_bool("LLM_MARKETING_ENABLED")

    creative_gen: Any
    if llm_client is not None and llm_enabled:
        try:
            from runtime.creative import LLMCreativeGenerator

            _provider, _base_url, _api_key, model, _anthropic_version = resolve_runtime_llm_settings(
                provider=env_str("LLM_PROVIDER", "openai_compat"),
                read_value=lambda name, default: env_str(name, default),
                openai_legacy_keys=("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"),
            )
            temperature = env_float("LLM_CREATIVE_TEMPERATURE", 0.5, lo=0.0, hi=2.0)
            timeout_s = env_float("LLM_CREATIVE_TIMEOUT_S", 15.0, lo=1.0, hi=120.0)

            creative_gen = LLMCreativeGenerator(
                llm=llm_client,
                model=model,
                temperature=temperature,
                timeout_s=timeout_s,
            )
            logger.info("[campaign_builder] LLMCreativeGenerator enabled (model=%s)", model)
        except Exception as exc:
            logger.warning("[campaign_builder] LLMCreativeGenerator init failed, using fallback: %r", exc)
            creative_gen = CreativeGenerator()
    else:
        creative_gen = CreativeGenerator()
        if not llm_enabled:
            logger.debug(
                "[campaign_builder] LLM disabled — using deterministic CreativeGenerator. "
                "Set LLM_ENABLED=1 to enable AI-generated ad creative."
            )

    traffic = TrafficStrategyService(
        campaign_factory=CampaignFactory(),
        audience_selector=AudienceSelector(),
        creative_generator=creative_gen,
        budget_allocator=BudgetAllocator(),
        bid_manager=BidManager(),
    )
    codec = TrafficToAdsSpec(builder=AdsSpecBuilder())
    return AutopilotCampaignBuilder(
        traffic=traffic,
        codec=codec,
        budget_policy=CampaignBudgetPolicy(),
    )
