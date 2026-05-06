from __future__ import annotations

"""Final owner for runtime dependency sets.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells."""

CANON_RUNTIME_DEPENDENCY_SETS_FINAL_OWNER = True
CANON_RUNTIME_DEPENDENCY_SETS_DATA_ONLY = True


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
DECISION_CORE_DEPS: Final[tuple[str, ...]] = get_runtime_service_spec(
    RuntimeServiceName.DECISION_CORE,
).dependencies

__all__ = [
    'AUTONOMY_ADVISOR_DEPS',
    'CREATIVE_INTELLIGENCE_DEPS',
    'DECISION_CORE_DEPS',
    'DECISION_GATEWAY_DEPS',
    'DECISION_INPUT_SERVICE_DEPS',
    'GOVERNANCE_CHAIN_DEPS',
    'OBSERVABILITY_ONLY',
    'RUNTIME_PACKET_PROVIDER_DEPS',
    'WORLD_STATE_INTEGRATION_DEPS',
]
