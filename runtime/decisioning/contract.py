from __future__ import annotations

from application.decisioning.candidate_collection import CandidateCollection
from kernel.decisioning.candidate_types import CandidateEnvelope, CandidateObservation, CandidateScore
from application.decisioning.decision_command import DecisionCommand
from kernel.decisioning.decision_types import Recommendation, RecommendationSet
from kernel.decisioning.route_contract import (
    CANONICAL_ROUTE,
    EXPECTED_ISSUER_ID,
    DecisionRoute,
    DecisionRouteViolation,
    canonical_runtime_route,
    extract_route_from_envelope,
    extract_strict_route_from_envelope,
)

CANON_RUNTIME_DECISIONING_CONTRACT = True

__all__ = [
    'CANON_RUNTIME_DECISIONING_CONTRACT',
    'CANONICAL_ROUTE',
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
