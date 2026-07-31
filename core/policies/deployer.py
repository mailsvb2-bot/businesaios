from __future__ import annotations
from config.decision_safety_policy import DEFAULT_AUTO_DEPLOYER_POLICY, AutoDeployerPolicy
from core.policies.shadow import ShadowEvaluator
class AutoDeployer:
    def __init__(self, shadow_threshold: float | None = None, policy: AutoDeployerPolicy | None = None):
        self._policy = policy or DEFAULT_AUTO_DEPLOYER_POLICY
        self.shadow_threshold = float(self._policy.shadow_threshold if shadow_threshold is None else shadow_threshold)
        self.shadow = ShadowEvaluator()
    def approve(self, dataset, policy) -> bool:
        return self.shadow.evaluate(dataset, policy) <= self.shadow_threshold
