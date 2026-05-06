from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from config import GravityWeights as GravityWeights
from config import MatchAdjustments as MatchAdjustments
from config import RoutingPolicyDeltas as RoutingPolicyDeltas
from config import GRAVITY_WEIGHTS as GRAVITY_WEIGHTS
from config import MATCH_ADJUSTMENTS as MATCH_ADJUSTMENTS
from config import ROUTING_POLICY_DELTAS as ROUTING_POLICY_DELTAS

__all__ = ['GravityWeights', 'MatchAdjustments', 'RoutingPolicyDeltas', 'GRAVITY_WEIGHTS', 'MATCH_ADJUSTMENTS', 'ROUTING_POLICY_DELTAS']
