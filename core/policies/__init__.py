"""Concrete policies.

Policies only propose actions; they never execute effects and never call runtime.
DecisionCore remains the only decision point.
"""

from __future__ import annotations

from core.policies.canary import CanaryPolicyResolver as CanaryRouter
from core.policies.deployer import AutoDeployer
from core.policies.domain import PolicyRef, PolicyStatus, RolloutConfig
from core.policies.evaluator import SafetyEvaluator
from core.policies.metrics import CanaryMetrics
from core.policies.registry import PolicyRegistry
from core.policies.rollout import SafeRolloutManager
from core.policies.shadow import ShadowEvaluator
from core.policies.trainer import OfflineTrainer
from core.scorers.bandit import EpsilonGreedyBandit

CANON_POLICY_PUBLIC_API = True

class ApprovalPolicy:
    def evaluate(self, candidate: object) -> tuple[bool, str]:
        return (not bool(candidate.payload.get('requires_approval', False)), 'requires_manual_approval')

class BudgetPolicy:
    def __init__(self, max_budget_delta: float = 0.20) -> None:
        self.max_budget_delta = max_budget_delta

    def evaluate(self, candidate: object) -> tuple[bool, str]:
        return (float(candidate.payload.get('budget_delta', 0.0)) <= self.max_budget_delta, 'budget_delta_too_high')

class ChannelPolicy:
    def __init__(self, forbidden_channels: tuple[str, ...] = ()) -> None:
        self.forbidden_channels = forbidden_channels

    def evaluate(self, candidate: object) -> tuple[bool, str]:
        return (candidate.channel not in self.forbidden_channels, 'forbidden_channel')

class ExperimentPolicy:
    def evaluate(self, candidate: object) -> tuple[bool, str]:
        return (not bool(candidate.payload.get('experiment_blocked', False)), 'experiment_blocked')

class RiskPolicy:
    def __init__(self, max_risk_score: float = 0.75) -> None:
        self.max_risk_score = max_risk_score

    def evaluate(self, candidate: object) -> tuple[bool, str]:
        return (float(candidate.payload.get('risk_score', 0.0)) <= self.max_risk_score, 'risk_too_high')

__all__ = [
    "CANON_POLICY_PUBLIC_API",
    "ApprovalPolicy",
    "AutoDeployer",
    "BudgetPolicy",
    "CanaryMetrics",
    "CanaryRouter",
    "ChannelPolicy",
    "EpsilonGreedyBandit",
    "ExperimentPolicy",
    "OfflineTrainer",
    "PolicyRef",
    "RiskPolicy",
    "PolicyRegistry",
    "PolicyStatus",
    "RolloutConfig",
    "SafeRolloutManager",
    "SafetyEvaluator",
    "ShadowEvaluator",
]
