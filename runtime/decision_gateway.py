from __future__ import annotations

"""Canonical runtime decision gateways.

This module keeps runtime orchestration code on a single canonical path:
packet -> contract -> safe enrichment -> decision issuer -> locked executor.
Historical helper APIs remain available as transitional ABI only.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from collections.abc import Callable
from collections.abc import Mapping

from bootstrap.decision_core_contract import RuntimeDecisionCorePort as DecisionIssuer

if TYPE_CHECKING:  # pragma: no cover
    from runtime.decision_input.decision_input_service import DecisionInputService
    from runtime.decision_input.runtime_state_enrichment import RuntimeStateEnrichmentService
    from runtime.integration.decision_input_packet import DecisionInputPacket
    from runtime.runtime_observability import RuntimeObservability
else:
    DecisionInputService = Any  # type: ignore[misc,assignment]
    RuntimeStateEnrichmentService = Any  # type: ignore[misc,assignment]
    DecisionInputPacket = Any  # type: ignore[misc,assignment]
    RuntimeObservability = Any  # type: ignore[misc,assignment]

CANON_RUNTIME_DECISION_GATEWAY_SINGLE_PATH = True
CANON_RUNTIME_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC = True
CANON_RUNTIME_DECISION_GATEWAY_OWNS_EXECUTION_SEQUENCE = True
CANON_RUNTIME_DECISION_ROUTE_GATEWAY_OWNER = True
CANON_RUNTIME_DECISION_GATEWAY_COMPAT_ALIAS = True
CANON_RUNTIME_DECISION_GATEWAY_NAME_RESERVED_FOR_ROUTE_OWNER = True


class DecisionGatewayContractError(RuntimeError):
    pass


@dataclass
class RuntimeDecisionRouteGateway:
    decision_input_service: DecisionInputService
    enrichment_service: RuntimeStateEnrichmentService
    observability: RuntimeObservability

    def route(
        self,
        *,
        packet: DecisionInputPacket,
        canonical_context: Mapping[str, object],
        decision_core_callable: Callable[[dict[str, object]], object],
    ) -> object:
        from canon.decision_gateway_rules import assert_decision_gateway_api

        assert_decision_gateway_api(("route",))
        if not callable(decision_core_callable):
            raise DecisionGatewayContractError("decision_core_not_callable")
        contract = self.decision_input_service.read_packet(packet)
        enrichment = self.enrichment_service.build(contract)
        if not isinstance(enrichment, Mapping):
            raise DecisionGatewayContractError("enrichment_must_be_mapping")
        next_context = dict(canonical_context)
        next_context.update(dict(enrichment))
        self.observability.record_model_snapshot(
            model_name="decision_gateway",
            metric_name="enrichment_key_count",
            metric_value=float(len(enrichment)),
        )
        packet_id = str(getattr(packet, "packet_id", "") or "decision_packet")
        self.observability.record_decision_trace(
            trace_name="decision_gateway",
            stage="contract_enriched",
            generated_at_ms=int(
                getattr(packet.recommendation_packet.world_state, "generated_at_ms", 0) or 0
            ),
            packet_id=packet_id,
            enrichment_key_count=len(enrichment),
            context_key_count=len(next_context),
        )
        return decision_core_callable(next_context)


@dataclass(slots=True, frozen=True)
class RuntimeDecisionIssueGateway:
    issuer: DecisionIssuer

    def issue(
        self,
        state: Any,
        *,
        decision_input_packet: DecisionInputPacket | None = None,
    ) -> Any:
        from runtime.decision_input.runtime_state_enrichment import enrich_state_with_decision_input_packet
        from runtime.decision_path_lock import issue_locked_decision

        enriched_state = enrich_state_with_decision_input_packet(
            state=state,
            decision_input_packet=decision_input_packet,
        )
        try:
            return issue_locked_decision(
                decision_core=self.issuer,
                state=enriched_state,
            ).envelope
        except Exception as exc:
            if isinstance(exc, DecisionGatewayContractError):
                raise
            raise DecisionGatewayContractError(str(exc)) from exc


# Transitional ABI only.
DecisionGateway = RuntimeDecisionRouteGateway
RuntimeDecisionGateway = RuntimeDecisionIssueGateway

COMPAT_DECISION_GATEWAY_FUNCTION = True


def issue_runtime_decision(
    *,
    issuer: DecisionIssuer,
    state: Any,
    decision_input_packet: DecisionInputPacket | None = None,
) -> Any:
    """Thin compatibility wrapper over RuntimeDecisionIssueGateway.issue."""
    return RuntimeDecisionIssueGateway(
        issuer=issuer
    ).issue(state, decision_input_packet=decision_input_packet)


def execute_runtime_decision(
    *,
    issuer: DecisionIssuer,
    executor: Any,
    state: Any,
    decision_input_packet: DecisionInputPacket | None = None,
) -> Any:
    """Canonical runtime helper for issue -> execute on one path."""
    from runtime.execution.execution_path_lock import (
        execute_locked_decision,
        lock_execution_envelope,
    )

    envelope = issue_runtime_decision(
        issuer=issuer,
        state=state,
        decision_input_packet=decision_input_packet,
    )
    try:
        locked_execution = lock_execution_envelope(envelope=envelope)
        return execute_locked_decision(executor=executor, locked_path=locked_execution)
    except Exception as exc:
        if isinstance(exc, DecisionGatewayContractError):
            raise
        raise DecisionGatewayContractError(str(exc)) from exc


def validate_runtime_decision_issuer(issuer: DecisionIssuer) -> None:
    issue = getattr(issuer, "issue", None)
    if not callable(issue):
        raise DecisionGatewayContractError("issuer_issue_missing")


def route_and_issue_runtime_decision(
    *,
    route_gateway: RuntimeDecisionRouteGateway,
    issuer: DecisionIssuer,
    packet: DecisionInputPacket,
    canonical_context: Mapping[str, object],
) -> Any:
    validate_runtime_decision_issuer(issuer)
    state = route_gateway.route(
        packet=packet,
        canonical_context=canonical_context,
        decision_core_callable=lambda enriched_state: enriched_state,
    )
    return issue_runtime_decision(
        issuer=issuer,
        state=state,
        decision_input_packet=packet,
    )


def build_runtime_decision_route_gateway(
    *,
    decision_input_service: DecisionInputService,
    enrichment_service: RuntimeStateEnrichmentService,
    observability: RuntimeObservability,
) -> RuntimeDecisionRouteGateway:
    return RuntimeDecisionRouteGateway(
        decision_input_service=decision_input_service,
        enrichment_service=enrichment_service,
        observability=observability,
    )


def build_runtime_decision_gateway(
    *,
    decision_input_service: DecisionInputService,
    enrichment_service: RuntimeStateEnrichmentService,
    observability: RuntimeObservability,
) -> RuntimeDecisionRouteGateway:
    """Compatibility wrapper over the canonical route-gateway builder."""
    return build_runtime_decision_route_gateway(
        decision_input_service=decision_input_service,
        enrichment_service=enrichment_service,
        observability=observability,
    )


def build_runtime_decision_issue_gateway(*, issuer: DecisionIssuer) -> RuntimeDecisionIssueGateway:
    validate_runtime_decision_issuer(issuer)
    return RuntimeDecisionIssueGateway(issuer=issuer)


__all__ = [
    "CANON_RUNTIME_DECISION_GATEWAY_COMPAT_ALIAS",
    "CANON_RUNTIME_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC",
    "CANON_RUNTIME_DECISION_GATEWAY_OWNS_EXECUTION_SEQUENCE",
    "CANON_RUNTIME_DECISION_GATEWAY_SINGLE_PATH",
    "CANON_RUNTIME_DECISION_ROUTE_GATEWAY_OWNER",
    "CANON_RUNTIME_DECISION_GATEWAY_NAME_RESERVED_FOR_ROUTE_OWNER",
    "COMPAT_DECISION_GATEWAY_FUNCTION",
    "DecisionGateway",
    "DecisionGatewayContractError",
    "DecisionIssuer",
    "RuntimeDecisionGateway",
    "RuntimeDecisionIssueGateway",
    "RuntimeDecisionRouteGateway",
    "route_and_issue_runtime_decision",
    "validate_runtime_decision_issuer",
    "build_runtime_decision_gateway",
    "build_runtime_decision_route_gateway",
    "build_runtime_decision_issue_gateway",
    "execute_runtime_decision",
    "issue_runtime_decision",
]
