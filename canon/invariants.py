from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonInvariant:
    name: str
    description: str
    severity: str = 'critical'


def default_invariants() -> list[CanonInvariant]:
    return [
        CanonInvariant('single_decision_core', 'Only core.ai.decision_core.DecisionCore may issue final executable decisions.'),
        CanonInvariant('single_execution_contract', 'Every action must be represented as contracts.executable_action.ExecutableAction.'),
        CanonInvariant('single_optimization_goal', 'The system must optimize profit-adjusted growth through one shared objective.'),
        CanonInvariant('single_data_flow', 'The closed loop must be signal -> opportunity -> decision -> execution -> feedback.'),
        CanonInvariant('no_second_brain', 'No alternate brain/core may rank and emit final actions.'),
        CanonInvariant('observability_required', 'Every decision and execution must produce telemetry.'),
        CanonInvariant('small_modules', 'Modules should stay small and single-purpose.', severity='important'),
    ]
