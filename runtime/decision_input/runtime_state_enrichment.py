from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from canon.runtime_state_enrichment_rules import assert_runtime_enrichment_payload
from contracts.decisioning.decision_input_contract import DecisionInputContract
from runtime.decision_input import build_decision_core_enrichment
from runtime.decision_input.decision_core_adapter import adapt_packet_for_decision_core
from runtime.integration.decision_input_packet import DecisionInputPacket
from runtime.runtime_observability import RuntimeObservability


CANON_RUNTIME_STATE_ENRICHMENT_SERVICE_OWNER = True


@dataclass
class RuntimeStateEnrichmentService:
    observability: RuntimeObservability

    def build(self, contract: DecisionInputContract) -> dict[str, object]:
        payload = build_decision_core_enrichment(contract)
        assert_runtime_enrichment_payload(payload)
        self.observability.record_model_snapshot(
            model_name="runtime_state_enrichment",
            metric_name="world_state_feature_count",
            metric_value=float(len(payload.get("external_world_state_features", {}))),
        )
        return payload


def enrich_state_with_decision_input_packet(*, state: Any, decision_input_packet: DecisionInputPacket | None) -> Any:
    if decision_input_packet is None:
        return state

    contract = adapt_packet_for_decision_core(decision_input_packet)
    enrichment = build_decision_core_enrichment(contract)
    assert_runtime_enrichment_payload(enrichment)

    if isinstance(state, dict):
        out = dict(state)
        meta = dict(out.get("meta") or {})
        meta.update(enrichment)
        out["meta"] = meta
        return out

    meta = dict(getattr(state, "meta", {}) or {})
    meta.update(enrichment)
    return replace(state, meta=meta)


def build_runtime_state_enrichment_service(
    *, observability: RuntimeObservability
) -> RuntimeStateEnrichmentService:
    return RuntimeStateEnrichmentService(observability=observability)


__all__ = [
    "CANON_RUNTIME_STATE_ENRICHMENT_SERVICE_OWNER",
    "RuntimeStateEnrichmentService",
    "build_runtime_state_enrichment_service",
    "enrich_state_with_decision_input_packet",
]
