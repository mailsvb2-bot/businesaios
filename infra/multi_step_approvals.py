from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MultiStepApprovalDecision:
    approved: bool
    missing_steps: tuple[str, ...] = field(default_factory=tuple)


def evaluate_multi_step_approval(
    *,
    required_steps: tuple[str, ...],
    approved_steps: tuple[str, ...],
) -> MultiStepApprovalDecision:
    required = set(required_steps)
    approved = set(approved_steps)
    missing = tuple(sorted(required - approved))
    return MultiStepApprovalDecision(
        approved=not missing,
        missing_steps=missing,
    )
