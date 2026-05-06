from __future__ import annotations

from contracts.decisioning.decision_input_contract import DecisionInputContract


def build_explanation_view(contract: DecisionInputContract) -> tuple[str, ...]:
    return tuple(contract.envelope.explanation_lines)
