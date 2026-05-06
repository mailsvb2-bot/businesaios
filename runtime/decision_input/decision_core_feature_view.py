from __future__ import annotations

from contracts.decisioning.decision_input_contract import DecisionInputContract


def build_feature_view(contract: DecisionInputContract) -> dict[str, float]:
    features = dict(contract.envelope.world_state_features)
    features.update(contract.envelope.advisory_features)
    return features
