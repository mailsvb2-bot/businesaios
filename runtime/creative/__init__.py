from __future__ import annotations

"""Canonical runtime creative-intelligence public surface."""

from core.creative_intelligence.input_replacement import replace_market_fit_score
from core.creative_intelligence.models import (
    CreativeEconomicsInput,
    CreativeEvidenceBundle,
    CreativeIntelligenceSnapshot,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)
from core.creative_intelligence.recommendation_builder import build_creative_recommendations
from core.creative_intelligence.snapshot_builder import build_creative_snapshot
from core.scorers.portfolio import rank_portfolio
from core.traffic.creative_generator import LLMCreativeGenerator

CANON_RUNTIME_CREATIVE_PUBLIC_API = True

__all__ = [
    'CANON_RUNTIME_CREATIVE_NAMESPACE',
    'CANON_RUNTIME_CREATIVE_PUBLIC_API',
    'CreativeEconomicsInput',
    'CreativeEvidenceBundle',
    'CreativeIntelligenceSnapshot',
    'CreativePnLSnapshot',
    'ExperimentConfidenceSnapshot',
    'IncrementalitySnapshot',
    'LLMCreativeGenerator',
    'build_creative_recommendations',
    'build_creative_snapshot',
    'rank_portfolio',
    'replace_market_fit_score',
]

CANON_RUNTIME_CREATIVE_NAMESPACE = True



