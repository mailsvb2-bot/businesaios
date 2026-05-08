from __future__ import annotations

from fastapi import APIRouter

from adapters.api.fastapi.network_side_effects_routes import (
    NETWORK_SIDE_EFFECTS_ROUTE,
    network_side_effects_payload,
    register_network_side_effects_routes,
)
from runtime.canonical_surface_manifest import (
    ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS,
    ALLOWED_NETWORK_LITERAL_SURFACES,
    ALLOWED_NETWORK_PRIMITIVE_IMPORTERS,
    ALLOWED_OPERATOR_NETWORK_PROBES,
)


def test_network_side_effects_payload_exposes_manifest_read_only() -> None:
    payload = network_side_effects_payload(tenant_id="tenant-demo", business_id="business-demo")

    assert payload["tenant_id"] == "tenant-demo"
    assert payload["business_id"] == "business-demo"
    assert payload["read_only"] is True
    assert payload["surface"] == "control_plane"
    assert payload["source"] == "runtime.canonical_surface_manifest"
    assert payload["seal_status"] == "enforced_by_tests"
    assert payload["allowed_network_primitive_importers"] == list(ALLOWED_NETWORK_PRIMITIVE_IMPORTERS)
    assert payload["allowed_network_literal_surfaces"] == list(ALLOWED_NETWORK_LITERAL_SURFACES)
    assert payload["allowed_operator_network_probes"] == list(ALLOWED_OPERATOR_NETWORK_PROBES)
    assert payload["allowed_effect_domain_entrypoints"] == list(ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS)


def test_network_side_effects_payload_summary_counts_match_manifest() -> None:
    payload = network_side_effects_payload(tenant_id="tenant-demo")
    summary = payload["summary"]

    assert summary["allowed_network_primitive_importers"] == len(ALLOWED_NETWORK_PRIMITIVE_IMPORTERS)
    assert summary["allowed_network_literal_surfaces"] == len(ALLOWED_NETWORK_LITERAL_SURFACES)
    assert summary["allowed_operator_network_probes"] == len(ALLOWED_OPERATOR_NETWORK_PROBES)
    assert summary["allowed_effect_domain_entrypoints"] == len(ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS)


def test_network_side_effects_route_is_registered_once() -> None:
    router = APIRouter()
    register_network_side_effects_routes(router=router)
    routes = [getattr(route, "path", "") for route in router.routes]
    assert routes.count(NETWORK_SIDE_EFFECTS_ROUTE) == 1


def test_network_side_effects_rules_lock_raw_io_boundaries() -> None:
    payload = network_side_effects_payload(tenant_id="tenant-demo")
    rules = payload["rules"]

    assert rules["decision_core_raw_network_forbidden"] is True
    assert rules["application_business_logic_raw_network_forbidden"] is True
    assert rules["admin_ui_raw_network_forbidden"] is True
    assert rules["connectors_must_use_sealed_transport"] is True
    assert rules["provider_endpoint_truth_lives_in_provider_transport_bindings"] is True
    assert rules["operator_probes_are_local_server_only"] is True
    assert rules["tests_are_not_allowed_as_production_bypass"] is True


def test_network_side_effects_control_plane_does_not_create_second_policy_source() -> None:
    payload = network_side_effects_payload(tenant_id="tenant-demo")
    assert payload["source"] == "runtime.canonical_surface_manifest"
    assert "runtime/business_autonomy/provider_transport_bindings.py" in payload["allowed_network_literal_surfaces"]
    assert "runtime/business_autonomy/provider_http_live_clients.py" in payload["allowed_network_primitive_importers"]
