"""
Ads Creative Autopilot
---------------------
Generates, validates, scores, and selects ad creatives (text-only) using:
- Offer catalog entries
- Behavioral signals (optional)
- Bandits (Thompson sampling) over creative arms
- Guardrails (policy + soft-backoff aware constraints)
"""

from .bandit import CreativeThompsonBandit
from .guardrails import validate_creative
from .models import CreativeCandidate, CreativeGuardrails, CreativeSelection
from .pipeline import CreativePipeline, CreativePipelineConfig, generate_candidates, select_creative

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
