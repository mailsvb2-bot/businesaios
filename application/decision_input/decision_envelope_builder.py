from __future__ import annotations

from application.decision_input.advisory_feature_extractor import extract_advisory_features
from application.decision_input.explanation_normalizer import normalize_explanations
from application.decision_input.metadata_builder import build_metadata
from application.decision_input.rules import assert_safe_metadata, assert_safe_recommendations
from application.decision_input.world_state_feature_extractor import extract_world_state_features
from contracts.decisioning.decision_envelope_contract import DecisionEnvelopeContract
from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract


def build_decision_envelope(
    packet: RecommendationPacketContract,
) -> DecisionEnvelopeContract:
    assert_safe_recommendations(packet.recommendations)

    metadata = build_metadata(packet.world_state)
    assert_safe_metadata(metadata)

    return DecisionEnvelopeContract(
        packet_id=packet.packet_id,
        world_state_features=extract_world_state_features(packet.world_state),
        advisory_features=extract_advisory_features(packet.recommendations),
        explanation_lines=normalize_explanations(packet.explanation_lines),
        metadata=metadata,
    )
