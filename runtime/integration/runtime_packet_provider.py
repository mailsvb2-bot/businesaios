from __future__ import annotations

from dataclasses import dataclass

from canon.runtime_packet_provider_rules import assert_runtime_packet_provider_api
from runtime.integration.decision_input_packet import DecisionInputPacket
from runtime.integration.runtime_packet_request import RuntimePacketRequest
from runtime.integration.world_state_integration_service import WorldStateIntegrationService
from runtime.runtime_observability import RuntimeObservability


@dataclass
class RuntimePacketProvider:
    integration_service: WorldStateIntegrationService
    observability: RuntimeObservability

    def build(self, request: RuntimePacketRequest) -> DecisionInputPacket:
        assert_runtime_packet_provider_api(("build",))
        self.observability.record_model_snapshot(
            model_name="runtime_packet_provider",
            metric_name="request_generated_at_ms",
            metric_value=float(request.generated_at_ms),
        )
        return self.integration_service.build_packet(
            generated_at_ms=request.generated_at_ms,
            user_observables=request.user_observables,
            market_snapshot=request.market_snapshot,
            creative_snapshots=request.creative_snapshots,
            architecture_state=request.architecture_state,
            structure_state=request.structure_state,
            flow_state=request.flow_state,
            diffusion_state=request.diffusion_state,
            advisory_packet=request.advisory_packet,
        )
