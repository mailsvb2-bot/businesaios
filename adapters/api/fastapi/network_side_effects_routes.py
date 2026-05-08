from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from runtime.canonical_surface_manifest import (
    ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS,
    ALLOWED_NETWORK_LITERAL_SURFACES,
    ALLOWED_NETWORK_PRIMITIVE_IMPORTERS,
    ALLOWED_OPERATOR_NETWORK_PROBES,
)

CANON_NETWORK_SIDE_EFFECTS_CONTROL_PLANE_ROUTES = True
NETWORK_SIDE_EFFECTS_ROUTE = "/control-plane/security/network-side-effects"
_RULES = {
    "decision_core_raw_network_forbidden": True, "application_business_logic_raw_network_forbidden": True,
    "admin_ui_raw_network_forbidden": True, "connectors_must_use_sealed_transport": True,
    "provider_endpoint_truth_lives_in_provider_transport_bindings": True,
    "operator_probes_are_local_server_only": True, "tests_are_not_allowed_as_production_bypass": True,
}


def network_side_effects_payload(*, tenant_id: str, business_id: str = "default-business") -> dict[str, Any]:
    groups = {
        "allowed_network_primitive_importers": tuple(ALLOWED_NETWORK_PRIMITIVE_IMPORTERS),
        "allowed_network_literal_surfaces": tuple(ALLOWED_NETWORK_LITERAL_SURFACES),
        "allowed_operator_network_probes": tuple(ALLOWED_OPERATOR_NETWORK_PROBES),
        "allowed_effect_domain_entrypoints": tuple(ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS),
    }
    return {
        "tenant_id": str(tenant_id or "").strip(), "business_id": str(business_id or "default-business").strip() or "default-business",
        "read_only": True, "status": "ok", "surface": "control_plane", "source": "runtime.canonical_surface_manifest",
        "seal_status": "enforced_by_tests", "summary": {name: len(values) for name, values in groups.items()},
        **{name: list(values) for name, values in groups.items()}, "rules": dict(_RULES),
    }


def register_network_side_effects_routes(*, router: APIRouter) -> None:
    @router.get(NETWORK_SIDE_EFFECTS_ROUTE, tags=["control-plane", "security"])
    async def control_plane_network_side_effects(tenant_id: str = "tenant-demo", business_id: str = "default-business") -> dict[str, Any]:
        return network_side_effects_payload(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_NETWORK_SIDE_EFFECTS_CONTROL_PLANE_ROUTES", "NETWORK_SIDE_EFFECTS_ROUTE", "network_side_effects_payload", "register_network_side_effects_routes"]
