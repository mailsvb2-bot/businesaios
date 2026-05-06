from __future__ import annotations

from typing import Any

from runtime.lazy_namespace import install_module_aliases

CANON_RUNTIME_SUPPORT_EXPLAINABILITY_NAMESPACE = True
CANON_COMPAT_SHIM = True

class ActionExplainer:
    def explain(self, action_name: str, reason: str) -> str:
        return f"action={action_name}; reason={reason}"

class CounterfactualExplainer:
    def explain(self, baseline: dict[str, Any], counterfactual: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
        keys = set(baseline) | set(counterfactual)
        return {
            key: (baseline.get(key), counterfactual.get(key))
            for key in sorted(keys)
            if baseline.get(key) != counterfactual.get(key)
        }

class EvaluationExplainer:
    def explain(self, metrics: dict[str, float]) -> str:
        return ", ".join(f"{key}={value:.4f}" for key, value in sorted(metrics.items()))

class FeatureAttribution:
    def attribute(self, features: dict[str, float]) -> list[tuple[str, float]]:
        return sorted(features.items(), key=lambda item: abs(item[1]), reverse=True)

class PolicyExplainer:
    def explain(self, policy_name: str, score: float) -> str:
        return f"policy={policy_name}, score={score:.4f}"

class PromotionExplainer:
    def explain(self, approved: bool, reason: str) -> str:
        return f"approved={approved}; reason={reason}"

class RewardExplainer:
    def explain(self, reward: float, components: dict[str, float]) -> str:
        details = ", ".join(f"{k}={v:.4f}" for k, v in sorted(components.items()))
        return f"reward={reward:.4f}; {details}"

class RollbackExplainer:
    def explain(self, rollback: bool, reason: str) -> str:
        return f"rollback={rollback}; reason={reason}"

install_module_aliases(__name__, {"decision_trace": "core.decision.runtime_decision_trace"})

__all__ = [
    "ActionExplainer",
    "CounterfactualExplainer",
    "EvaluationExplainer",
    "FeatureAttribution",
    "PolicyExplainer",
    "PromotionExplainer",
    "RewardExplainer",
    "RollbackExplainer",
]
