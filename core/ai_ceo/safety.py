from __future__ import annotations

"""Safe autonomy primitives for AI CEO (pure decisions).

This module contains *policy* checks only. No side effects.
"""

from dataclasses import dataclass
from typing import Any, Optional

from config.env_flags import env_bool, env_int


@dataclass(frozen=True)
class AutonomyPolicyV1:
    schema_version: int = 1
    dry_run: bool = True
    # Allow execution of risky actions only if explicitly enabled.
    allow_ads: bool = True
    allow_pricing: bool = False
    allow_llm: bool = True
    max_daily_spend_minor: int | None = None


def from_env() -> AutonomyPolicyV1:
    max_daily_spend_minor = env_int("AI_CEO_MAX_DAILY_SPEND_MINOR", 0, lo=0)
    return AutonomyPolicyV1(
        dry_run=env_bool("AI_CEO_DRY_RUN", True),
        allow_ads=env_bool("AI_CEO_ALLOW_ADS", True),
        allow_pricing=env_bool("AI_CEO_ALLOW_PRICING", False),
        allow_llm=env_bool("AI_CEO_ALLOW_LLM", True),
        max_daily_spend_minor=max_daily_spend_minor or None,
    )


def check_step_allowed(step_action: str, *, policy: AutonomyPolicyV1) -> str | None:
    a = str(step_action or "")
    if a.startswith("ads_") or "ads" in a:
        if not policy.allow_ads:
            return "ads_disabled"
    if "pricing" in a:
        if not policy.allow_pricing:
            return "pricing_disabled"
    if "llm" in a:
        if not policy.allow_llm:
            return "llm_disabled"
    return None
