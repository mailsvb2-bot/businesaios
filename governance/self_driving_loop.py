"""Self-driving governed learning loop.

Canonical governed cycle:

    rewards -> train -> evaluate -> approve -> swap -> monitor -> rollback

Architectural rules:
- this module contains orchestration only
- approval stays explicit
- actuation remains outside this module except registry.swap rollback/swap hooks
- governance stays subordinate to the canonical decision authority
- no second brain: this loop does not invent goals or strategy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol

from governance.self_driving_contract import GovernedEvolutionReport


SELF_DRIVING_LOOP_CANON_VERSION = "SDL-CANON-V3"


class Policy(Protocol):
    """Opaque policy object."""


class RewardStore(Protocol):
    def all(self) -> Any:
        ...


class OfflineTrainer(Protocol):
    def train(self, rewards: Any) -> Policy:
        ...


class PolicyEvaluator(Protocol):
    def evaluate(self, policy: Policy, rewards: Any) -> "PolicyMetrics":
        ...


class PolicyRegistry(Protocol):
    @property
    def active(self) -> Policy:
        ...

    def swap(self, policy: Policy) -> None:
        ...


class RolloutManager(Protocol):
    def approve(self, old: "PolicyMetrics", new: "PolicyMetrics") -> bool:
        ...


@dataclass(frozen=True)
class PolicyMetrics:
    reward: float
    risk: float = 0.0
    stability: float = 1.0
    metadata: Mapping[str, object] = field(default_factory=dict)


class RollbackController:
    """Stores previous policy reference for external rollback actuation."""

    def __init__(self, registry: PolicyRegistry):
        self._registry = registry
        self._previous: Optional[Policy] = None

    def before_swap(self) -> None:
        self._previous = self._registry.active

    def rollback(self) -> None:
        if self._previous is not None:
            self._registry.swap(self._previous)


class SelfDrivingLoop:
    """Closed autonomous improvement cycle with explicit approval gate."""

    def __init__(
        self,
        store: RewardStore,
        trainer: OfflineTrainer,
        evaluator: PolicyEvaluator,
        registry: PolicyRegistry,
        rollout: RolloutManager,
        rollback: RollbackController,
        *,
        constitution: Any | None = None,
        evolution_gate: Any | None = None,
        survival_controller: Any | None = None,
    ):
        self._store = store
        self._trainer = trainer
        self._evaluator = evaluator
        self._registry = registry
        self._rollout = rollout
        self._rollback = rollback
        self._constitution = constitution
        self._evolution_gate = evolution_gate
        self._survival_controller = survival_controller
        self._last_report = GovernedEvolutionReport(
            evolved=False,
            reason="not_run_yet",
            approval_required=True,
            approved=False,
            rollback_triggered=False,
        )

    @property
    def last_report(self) -> GovernedEvolutionReport:
        return self._last_report

    def evolve(self) -> bool:
        return self.evolve_once().evolved

    def evolve_once(self) -> GovernedEvolutionReport:
        rewards = self._store.all()

        old_policy = self._registry.active
        new_policy = self._trainer.train(rewards)

        old_metrics = self._evaluator.evaluate(old_policy, rewards)
        new_metrics = self._evaluator.evaluate(new_policy, rewards)

        if self._evolution_gate is not None:
            gate_approved = bool(self._evolution_gate.approve(old_metrics, new_metrics))
            if self._constitution is not None:
                self._constitution.assert_safe_evolution(gate_approved)

        approved = bool(self._rollout.approve(old_metrics, new_metrics))
        if not approved:
            self._last_report = GovernedEvolutionReport(
                evolved=False,
                reason="approval_rejected",
                approval_required=True,
                approved=False,
                rollback_triggered=False,
                metadata={"old_metrics": old_metrics, "new_metrics": new_metrics},
            )
            return self._last_report

        self._rollback.before_swap()
        self._registry.swap(new_policy)

        rollback_triggered = False
        if self._survival_controller is not None and bool(self._survival_controller.should_rollback()):
            self._rollback.rollback()
            rollback_triggered = True

        self._last_report = GovernedEvolutionReport(
            evolved=not rollback_triggered,
            reason="swapped" if not rollback_triggered else "rolled_back_by_survival_controller",
            approval_required=True,
            approved=True,
            rollback_triggered=rollback_triggered,
            metadata={"old_metrics": old_metrics, "new_metrics": new_metrics},
        )
        return self._last_report
