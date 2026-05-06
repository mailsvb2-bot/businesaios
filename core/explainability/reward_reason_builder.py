from __future__ import annotations

from contracts.decisioning.reward_signal_contract import RewardSignalContract
from core.explainability.operator_reason import OperatorReason


def build_reward_reasons(signal: RewardSignalContract) -> tuple[OperatorReason, ...]:
    return (
        OperatorReason(code="reward_immediate", line=f"immediate_reward={signal.immediate_reward:.3f}"),
        OperatorReason(code="reward_future", line=f"expected_future_value={signal.expected_future_value:.3f}"),
        OperatorReason(code="reward_risk", line=f"risk_cost={signal.risk_cost:.3f}"),
        OperatorReason(code="reward_uncertainty", line=f"uncertainty_penalty={signal.uncertainty_penalty:.3f}"),
        OperatorReason(code="reward_constraints", line=f"constraint_cost={signal.constraint_cost:.3f}"),
    )
