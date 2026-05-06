from __future__ import annotations

from pathlib import Path


def test_demand_router_delegates_candidate_build_and_rank_to_matching_surface() -> None:
    source = Path('routing/demand_router.py').read_text(encoding='utf-8')
    assert 'from matching.routing_surface import RoutingCandidateBuilder, RoutingCandidateRanker' in source
    assert 'self._candidate_builder = RoutingCandidateBuilder()' in source
    assert 'self._candidate_ranker = RoutingCandidateRanker()' in source
    assert 'def _build_routing_candidate(' not in source
    assert 'def _rank_candidates(' not in source
