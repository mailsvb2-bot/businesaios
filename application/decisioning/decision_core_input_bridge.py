from __future__ import annotations

from application.decisioning.action_boundary_guard import assert_safe_action_boundary
from application.decisioning.decision_core_enrichment_guard import assert_safe_decision_core_enrichment
from contracts.decisioning.decision_input_contract import DecisionInputContract
from runtime.decision_input.decision_core_explanation_view import build_explanation_view
from runtime.decision_input.decision_core_feature_view import build_feature_view


def build_decision_core_enrichment(
    contract: DecisionInputContract,
) -> dict[str, object]:
    payload = {
        "external_world_state_features": build_feature_view(contract),
        "external_explanations": build_explanation_view(contract),
        "external_packet_id": contract.envelope.packet_id,
    }
    assert_safe_action_boundary(payload)
    assert_safe_decision_core_enrichment(payload)
    return payload
