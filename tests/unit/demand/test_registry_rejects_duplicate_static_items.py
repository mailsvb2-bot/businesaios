from __future__ import annotations

import pytest

from registry.match_scorer_registry import MatchScorerRegistry
from registry.routing_policy_registry import RoutingPolicyRegistry


def test_match_scorer_registry_rejects_duplicate_names() -> None:
    registry = MatchScorerRegistry()
    registry.register('alpha', object())
    with pytest.raises(ValueError, match='duplicate match_scorer: alpha'):
        registry.register('alpha', object())


def test_routing_policy_registry_rejects_duplicate_names() -> None:
    registry = RoutingPolicyRegistry()
    registry.register('alpha', object())
    with pytest.raises(ValueError, match='duplicate routing_policy: alpha'):
        registry.register('alpha', object())
