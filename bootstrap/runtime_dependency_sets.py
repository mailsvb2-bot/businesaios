from __future__ import annotations

"""Final owner for runtime dependency sets.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells.
"""

CANON_RUNTIME_DEPENDENCY_SETS_FINAL_OWNER = True
CANON_RUNTIME_DEPENDENCY_SETS_DATA_ONLY = True


from collections.abc import Mapping
from typing import Final

from bootstrap.runtime_service_specs import get_runtime_service_spec
from runtime.service_names import RuntimeServiceName


OBSERVABILITY_ONLY: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.ARCHITECTURE_WATCH,
).dependencies
CREATIVE_INTELLIGENCE_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.CREATIVE_INTELLIGENCE,
).dependencies
AUTONOMY_ADVISOR_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.AUTONOMY_ADVISOR,
).dependencies
WORLD_STATE_INTEGRATION_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.WORLD_STATE_INTEGRATION,
).dependencies
DECISION_INPUT_SERVICE_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.DECISION_INPUT_SERVICE,
).dependencies
RUNTIME_PACKET_PROVIDER_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.RUNTIME_PACKET_PROVIDER,
).dependencies
DECISION_GATEWAY_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.DECISION_GATEWAY,
).dependencies
GOVERNANCE_CHAIN_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.GOVERNANCE_CHAIN,
).dependencies
ACTION_BUDGET_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.ACTION_BUDGET,
).dependencies
DECISION_CORE_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.DECISION_CORE,
).dependencies

RUNTIME_DEPENDENCY_SETS: Final[Mapping[str, tuple[str, ...]]] = {
    "action_budget": ACTION_BUDGET_DEPS,
    "autonomy_advisor": AUTONOMY_ADVISOR_DEPS,
    "creative_intelligence": CREATIVE_INTELLIGENCE_DEPS,
    "decision_core": DECISION_CORE_DEPS,
    "decision_gateway": DECISION_GATEWAY_DEPS,
    "decision_input_service": DECISION_INPUT_SERVICE_DEPS,
    "governance_chain": GOVERNANCE_CHAIN_DEPS,
    "observability_only": OBSERVABILITY_ONLY,
    "runtime_packet_provider": RUNTIME_PACKET_PROVIDER_DEPS,
    "world_state_integration": WORLD_STATE_INTEGRATION_DEPS,
}

__all__ = [
    'ACTION_BUDGET_DEPS',
    'AUTONOMY_ADVISOR_DEPS',
    'CREATIVE_INTELLIGENCE_DEPS',
    'DECISION_CORE_DEPS',
    'DECISION_GATEWAY_DEPS',
    'DECISION_INPUT_SERVICE_DEPS',
    'GOVERNANCE_CHAIN_DEPS',
    'OBSERVABILITY_ONLY',
    'RUNTIME_DEPENDENCY_SETS',
    'RUNTIME_PACKET_PROVIDER_DEPS',
    'WORLD_STATE_INTEGRATION_DEPS',
]
