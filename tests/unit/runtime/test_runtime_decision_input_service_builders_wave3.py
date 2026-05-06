from __future__ import annotations

from runtime.decision_gateway import build_runtime_decision_gateway
from runtime.decision_input.decision_input_service import build_decision_input_service
from runtime.decision_input.runtime_state_enrichment import build_runtime_state_enrichment_service


class _Observability:
    def __init__(self) -> None:
        self.snapshots = []

    def record_model_snapshot(self, **payload):
        self.snapshots.append(payload)


def test_runtime_decision_input_service_builder_reuses_observability() -> None:
    observability = _Observability()
    service = build_decision_input_service(observability=observability)
    assert service.observability is observability


def test_runtime_state_enrichment_builder_reuses_observability() -> None:
    observability = _Observability()
    service = build_runtime_state_enrichment_service(observability=observability)
    assert service.observability is observability


def test_runtime_decision_gateway_builder_reuses_service_owners() -> None:
    observability = _Observability()
    decision_input_service = build_decision_input_service(observability=observability)
    enrichment_service = build_runtime_state_enrichment_service(observability=observability)
    gateway = build_runtime_decision_gateway(
        decision_input_service=decision_input_service,
        enrichment_service=enrichment_service,
        observability=observability,
    )
    assert gateway.decision_input_service is decision_input_service
    assert gateway.enrichment_service is enrichment_service
    assert gateway.observability is observability
