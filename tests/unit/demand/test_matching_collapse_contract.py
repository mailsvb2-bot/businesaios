from __future__ import annotations

from matching import (
    MatchBundleBuilder,
    MatchCandidateBuilder,
    MatchEngine,
    MatchExplainer,
    MatchFilter,
    MatchFilters,
    MatchRanker,
    MatchRanking,
    MatchScoreAggregator,
    MatchThresholds,
)
from matching.candidate_builder import (
    MatchBundleBuilder as CanonicalMatchBundleBuilder,
)
from matching.candidate_builder import (
    MatchCandidateBuilder as CanonicalMatchCandidateBuilder,
)
from matching.candidate_builder import (
    MatchExplainer as CanonicalMatchExplainer,
)
from matching.candidate_builder import (
    MatchScoreAggregator as CanonicalMatchScoreAggregator,
)
from matching.filters import (
    MatchFilter as CanonicalMatchFilter,
)
from matching.filters import (
    MatchFilters as CanonicalMatchFilters,
)
from matching.filters import (
    MatchThresholds as CanonicalMatchThresholds,
)
from matching.match_engine import MatchEngine as CanonicalMatchEngine
from matching.ranking import MatchRanker as CanonicalMatchRanker
from matching.ranking import MatchRanking as CanonicalMatchRanking


def test_matching_package_exports_canonical_collapsed_api() -> None:
    assert MatchBundleBuilder is CanonicalMatchBundleBuilder
    assert MatchCandidateBuilder is CanonicalMatchCandidateBuilder
    assert MatchEngine is CanonicalMatchEngine
    assert MatchExplainer is CanonicalMatchExplainer
    assert MatchFilter is CanonicalMatchFilter
    assert MatchFilters is CanonicalMatchFilters
    assert MatchRanker is CanonicalMatchRanker
    assert MatchRanking is CanonicalMatchRanking
    assert MatchScoreAggregator is CanonicalMatchScoreAggregator
    assert MatchThresholds is CanonicalMatchThresholds



def test_match_ranking_exposes_public_finite_guard() -> None:
    ranking = MatchRanking()
    assert ranking.finite('3.5') == 3.5
    assert ranking.finite(float('inf')) == 0.0
    assert ranking.finite('not-a-number') == 0.0
