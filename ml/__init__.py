from __future__ import annotations
import importlib, sys
from typing import Any
CANON_ML_ALIAS_NAMESPACE = True
_ALIAS_MAP = {"dataset_builder": "learning.trainer", "event_store": "learning.replay", "policy_promotion_guard": "learning.policy_update", "policy_rollout_manager": "learning.rollout", "rollout_manager": "learning.rollout"}
_PUBLIC_ATTRS = {"DatasetBuilder": ("learning.trainer", "DatasetBuilder"), "DatasetSnapshot": ("learning.trainer", "DatasetSnapshot"), "EvaluationResult": ("learning.policy_update", "EvaluationResult"), "EvaluationSnapshot": ("learning.policy_update", "EvaluationSnapshot"), "Event": ("learning.replay", "Event"), "EventStore": ("learning.replay", "EventStore"), "OfflineEventStore": ("learning.replay", "OfflineEventStore"), "PolicyPromotionGuard": ("learning.policy_update", "PolicyPromotionGuard"), "PolicyRollout": ("learning.rollout", "PolicyRollout"), "PolicyRolloutManager": ("learning.rollout", "PolicyRolloutManager"), "PromotionBlocked": ("learning.policy_update", "PromotionBlocked"), "PromotionDecision": ("learning.policy_update", "PromotionDecision"), "RolloutGuardViolation": ("learning.rollout", "RolloutGuardViolation"), "RolloutManager": ("learning.rollout", "RolloutManager"), "RolloutState": ("learning.rollout", "RolloutState"), "RuntimeEventStoreAdapter": ("learning.replay", "RuntimeEventStoreAdapter")}
for alias_name, target in _ALIAS_MAP.items():
    module = importlib.import_module(target); sys.modules[f"{__name__}.{alias_name}"] = module; setattr(sys.modules[__name__], alias_name, module)
def __getattr__(name: str) -> Any:
    target = _PUBLIC_ATTRS.get(name)
    if target is None: raise AttributeError(name)
    module_name, attr_name = target; value = getattr(importlib.import_module(module_name), attr_name); globals()[name] = value; return value
__all__ = ["CANON_ML_ALIAS_NAMESPACE", *_PUBLIC_ATTRS]
