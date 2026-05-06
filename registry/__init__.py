import importlib, sys

from registry.business_state_feed_registry import BusinessStateFeedRegistry
from registry.match_scorer_registry import MatchScorerRegistry
from registry.routing_policy_registry import RoutingPolicyRegistry
from shared.registry import ExperimentRegistry, ModelRegistry, PolicyRegistry

for _name in ("experiment_registry", "model_registry", "policy_registry"):
    _module = importlib.import_module("shared.registry")
    sys.modules[f"{__name__}.{_name}"] = _module
    setattr(sys.modules[__name__], _name, _module)

CANON_REGISTRY_NAMESPACE = True
__all__ = ["CANON_REGISTRY_NAMESPACE", "BusinessStateFeedRegistry", "ExperimentRegistry", "MatchScorerRegistry", "ModelRegistry", "PolicyRegistry", "RoutingPolicyRegistry"]
