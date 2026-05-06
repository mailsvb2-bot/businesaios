from __future__ import annotations

from boot.runtime_boot_manifest import RUNTIME_BOOT_MANIFEST
from boot.runtime_dependency_sets import (
    AUTONOMY_ADVISOR_DEPS,
    CREATIVE_INTELLIGENCE_DEPS,
    DECISION_CORE_DEPS,
    DECISION_GATEWAY_DEPS,
    DECISION_INPUT_SERVICE_DEPS,
    GOVERNANCE_CHAIN_DEPS,
    OBSERVABILITY_ONLY,
    RUNTIME_PACKET_PROVIDER_DEPS,
    WORLD_STATE_INTEGRATION_DEPS,
)
from boot.runtime_service_specs import (
    CATALOG_BACKED_RUNTIME_SERVICES,
    RUNTIME_BOOT_SERVICE_SPECS,
    get_runtime_service_spec,
)
from runtime.service_names import RuntimeServiceName


def test_dependency_sets_are_derived_from_service_specs() -> None:
    assert OBSERVABILITY_ONLY == get_runtime_service_spec(RuntimeServiceName.ARCHITECTURE_WATCH).dependencies
    assert CREATIVE_INTELLIGENCE_DEPS == get_runtime_service_spec(RuntimeServiceName.CREATIVE_INTELLIGENCE).dependencies
    assert AUTONOMY_ADVISOR_DEPS == get_runtime_service_spec(RuntimeServiceName.AUTONOMY_ADVISOR).dependencies
    assert WORLD_STATE_INTEGRATION_DEPS == get_runtime_service_spec(RuntimeServiceName.WORLD_STATE_INTEGRATION).dependencies
    assert DECISION_INPUT_SERVICE_DEPS == get_runtime_service_spec(RuntimeServiceName.DECISION_INPUT_SERVICE).dependencies
    assert RUNTIME_PACKET_PROVIDER_DEPS == get_runtime_service_spec(RuntimeServiceName.RUNTIME_PACKET_PROVIDER).dependencies
    assert DECISION_GATEWAY_DEPS == get_runtime_service_spec(RuntimeServiceName.DECISION_GATEWAY).dependencies
    assert GOVERNANCE_CHAIN_DEPS == get_runtime_service_spec(RuntimeServiceName.GOVERNANCE_CHAIN).dependencies
    assert DECISION_CORE_DEPS == get_runtime_service_spec(RuntimeServiceName.DECISION_CORE).dependencies


def test_runtime_boot_manifest_is_derived_from_service_specs() -> None:
    assert tuple(spec.as_manifest_entry() for spec in RUNTIME_BOOT_SERVICE_SPECS) == RUNTIME_BOOT_MANIFEST


def test_catalog_backed_runtime_services_stay_aligned_with_dependency_maps() -> None:
    expected = tuple(
        sorted(
            spec.service_name
            for spec in RUNTIME_BOOT_SERVICE_SPECS
            if spec.dependency_map
            or spec.service_name
            in {
                RuntimeServiceName.ARCHITECTURE_WATCH,
                RuntimeServiceName.STRUCTURE_WATCH,
                RuntimeServiceName.FLOW_WATCH,
                RuntimeServiceName.DIFFUSION_WATCH,
                RuntimeServiceName.MARKET_WATCH,
            }
        )
    )
    assert tuple(sorted(CATALOG_BACKED_RUNTIME_SERVICES)) == expected
