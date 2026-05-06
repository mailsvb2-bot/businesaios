"""
Ads Creative Autopilot
---------------------
Generates, validates, scores, and selects ad creatives (text-only) using:
- Offer catalog entries
- Behavioral signals (optional)
- Bandits (Thompson sampling) over creative arms
- Guardrails (policy + soft-backoff aware constraints)
"""

from .models import CreativeCandidate, CreativeSelection, CreativeGuardrails
from .guardrails import validate_creative
from .bandit import CreativeThompsonBandit
from .pipeline import generate_candidates, select_creative, CreativePipeline, CreativePipelineConfig

__all__ = [
    "CreativeCandidate",
    "CreativeSelection",
    "CreativeGuardrails",
    "validate_creative",
    "CreativeThompsonBandit",
    "generate_candidates",
    "select_creative",
    "CreativePipeline",
    "CreativePipelineConfig",
]
