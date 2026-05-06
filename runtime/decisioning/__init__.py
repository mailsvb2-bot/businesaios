from __future__ import annotations

"""Canonical runtime decisioning surface.

Runtime handlers may validate canonical decision routes and share tiny transport
shapes, but must not fork selection logic.
"""

from runtime.decisioning.contract import (
    CANONICAL_ROUTE,
    CANON_RUNTIME_DECISIONING_CONTRACT,
    EXPECTED_ISSUER_ID,
    CandidateCollection,
    CandidateEnvelope,
    CandidateObservation,
    CandidateScore,
    DecisionCommand,
    DecisionRoute,
    DecisionRouteViolation,
    Recommendation,
    RecommendationSet,
    canonical_runtime_route,
    extract_route_from_envelope,
    extract_strict_route_from_envelope,
)

CANON_RUNTIME_DECISIONING_PUBLIC_API = True

__all__ = [
    'CANONICAL_ROUTE',
    'CANON_RUNTIME_DECISIONING_CONTRACT',
    'CANON_RUNTIME_DECISIONING_PUBLIC_API',
    'EXPECTED_ISSUER_ID',
    'CandidateCollection',
    'CandidateEnvelope',
    'CandidateObservation',
    'CandidateScore',
    'DecisionCommand',
    'DecisionRoute',
    'DecisionRouteViolation',
    'Recommendation',
    'RecommendationSet',
    'canonical_runtime_route',
    'extract_route_from_envelope',
    'extract_strict_route_from_envelope',
]



