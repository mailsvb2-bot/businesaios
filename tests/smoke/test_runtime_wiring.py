from __future__ import annotations

from runtime.runtime_boot import boot_runtime
from runtime.service_names import RuntimeServiceName
from application.decisioning.decision_core_input_bridge import build_decision_core_enrichment

EXPECTED_SERVICES = (
    RuntimeServiceName.ARCHITECTURE_WATCH,
    RuntimeServiceName.STRUCTURE_WATCH,
    RuntimeServiceName.FLOW_WATCH,
    RuntimeServiceName.DIFFUSION_WATCH,
    RuntimeServiceName.MARKET_WATCH,
    RuntimeServiceName.CREATIVE_INTELLIGENCE,
    RuntimeServiceName.AUTONOMY_ADVISOR,
    RuntimeServiceName.WORLD_STATE_INTEGRATION,
    RuntimeServiceName.DECISION_INPUT_SERVICE,
)

FORBIDDEN_FIELDS = (
    "winner",
    "final_decision",
    "executor_command",
    "candidate_ids",
    "allowed_candidates",
    "filtered_candidates",
)

SAFE_FIELDS = (
    "external_world_state_features",
    "external_explanations",
    "external_packet_id",
)


def test_runtime_boot_success() -> None:
    registry = boot_runtime()
    assert registry is not None


def test_runtime_registry_contains_new_services() -> None:
    registry = boot_runtime()
    for name in EXPECTED_SERVICES:
        assert registry.get(name) is not None, f"{name} not registered"


def test_decision_input_pipeline_smoke() -> None:
    registry = boot_runtime()
    integration = registry.get(RuntimeServiceName.WORLD_STATE_INTEGRATION)
    decision_input = registry.get(RuntimeServiceName.DECISION_INPUT_SERVICE)
    packet = integration.build_packet()
    contract = decision_input.read_packet(packet)
    assert contract is not None


def test_decision_core_enrichment_build() -> None:
    registry = boot_runtime()
    integration = registry.get(RuntimeServiceName.WORLD_STATE_INTEGRATION)
    decision_input = registry.get(RuntimeServiceName.DECISION_INPUT_SERVICE)
    enrichment = build_decision_core_enrichment(decision_input.read_packet(integration.build_packet()))
    assert isinstance(enrichment, dict)


def test_no_second_brain_fields() -> None:
    registry = boot_runtime()
    integration = registry.get(RuntimeServiceName.WORLD_STATE_INTEGRATION)
    decision_input = registry.get(RuntimeServiceName.DECISION_INPUT_SERVICE)
    enrichment = build_decision_core_enrichment(decision_input.read_packet(integration.build_packet()))
    for field in FORBIDDEN_FIELDS:
        assert field not in enrichment, f"Forbidden field detected: {field}"


def test_enrichment_fields_are_safe() -> None:
    registry = boot_runtime()
    integration = registry.get(RuntimeServiceName.WORLD_STATE_INTEGRATION)
    decision_input = registry.get(RuntimeServiceName.DECISION_INPUT_SERVICE)
    enrichment = build_decision_core_enrichment(decision_input.read_packet(integration.build_packet()))
    for key in enrichment.keys():
        assert key in SAFE_FIELDS, f"Unexpected enrichment field: {key}"


def test_autonomy_advisor_is_not_decision_engine() -> None:
    registry = boot_runtime()
    advisor = registry.get(RuntimeServiceName.AUTONOMY_ADVISOR)
    packet = advisor.build_advisory_packet()
    assert packet is not None
    forbidden = ("winner", "decision", "execute")
    for key in packet.keys():
        assert key not in forbidden
