from __future__ import annotations

"""Canonical advisory owner surface for acquisition explanations."""

from advisory.acquisition_recommendation_builder import (
    AcquisitionRecommendation,
    AcquisitionRecommendations,
    CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER,
    build_acquisition_recommendations,
)
from advisory.acquisition_result_copy_renderer import (
    CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER,
    RenderedAcquisitionExplanation,
    render_acquisition_explanation,
)
from advisory.acquisition_result_projection import (
    AcquisitionExplanation,
    CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION,
    explain_acquisition_result,
)
from advisory.revenue_os import (
    CANON_ADVISORY_REVENUE_OS_OWNER_SURFACE,
    RevenueOSFacade,
    RevenueOSReport,
)

CANON_ADVISORY_OWNER_SURFACE = True

__all__ = [
    "AcquisitionExplanation",
    "AcquisitionRecommendation",
    "AcquisitionRecommendations",
    "CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER",
    "CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER",
    "CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION",
    "CANON_ADVISORY_OWNER_SURFACE",
    "CANON_ADVISORY_REVENUE_OS_OWNER_SURFACE",
    "RevenueOSFacade",
    "RevenueOSReport",
    "RenderedAcquisitionExplanation",
    "build_acquisition_recommendations",
    "explain_acquisition_result",
    "render_acquisition_explanation",
]
