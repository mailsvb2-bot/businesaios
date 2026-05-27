from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.decision_input_contract import DecisionInputContract
from runtime.decision_input.decision_core_adapter import adapt_packet_for_decision_core
from runtime.integration.decision_input_packet import DecisionInputPacket
from runtime.runtime_observability import RuntimeObservability

CANON_RUNTIME_DECISION_INPUT_SERVICE_OWNER = True


@dataclass
class DecisionInputService:
    observability: RuntimeObservability

    def read_packet(self, packet: DecisionInputPacket) -> DecisionInputContract:
        contract = adapt_packet_for_decision_core(packet)
        self.observability.record_model_snapshot(
            model_name="decision_input_service",
            metric_name="world_state_feature_count",
            metric_value=float(len(contract.envelope.world_state_features)),
        )
        self.observability.record_model_snapshot(
            model_name="decision_input_service",
            metric_name="advisory_feature_count",
            metric_value=float(len(contract.envelope.advisory_features)),
        )
        return contract


def build_decision_input_service(*, observability: RuntimeObservability) -> DecisionInputService:
    return DecisionInputService(observability=observability)


__all__ = [
    "CANON_RUNTIME_DECISION_INPUT_SERVICE_OWNER",
    "DecisionInputService",
    "build_decision_input_service",
]
