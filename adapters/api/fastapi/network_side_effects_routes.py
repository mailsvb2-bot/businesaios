from __future__ import annotations

"""Read-only control-plane visibility for the canonical network side-effect seal.

This module must not scan, decide, or maintain a second policy source.  It only
serializes the canonical surface manifest so operators can see which files are
allowed to perform sealed network work.
"""

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


def network_side_effects_payload(*, tenant_id: str, business_id: str = "default-business") -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    business = str(business_id or "default-business").strip() or "default-business"
    primitive_importers = tuple(ALLOWED_NETWORK_PRIMITIVE_IMPORTERS)
    literal_surfaces = tuple(ALLOWED_NETWORK_LITERAL_SURFACES)
    operator_probes = tuple(ALLOWED_OPERATOR_NETWORK_PROBES)
    effect_entrypoints = tuple(ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS)
    return {
        "tenant_id": tenant,
        "business_id": business,
        "read_only": True,
        "status": "ok",
        "surface": "control_plane",
        "source": "runtime.canonical_surface_manifest",
        "seal_status": "enforced_by_tests",
        "summary": {
            "allowed_network_primitive_importers": len(primitive_importers),
            "allowed_network_literal_surfaces": len(literal_surfaces),
            "allowed_operator_network_probes": len(operator_probes),
            "allowed_effect_domain_entrypoints": len(effect_entrypoints),
        },
        "allowed_network_primitive_importers": list(primitive_importers),
        "allowed_network_literal_surfaces": list(literal_surfaces),
        "allowed_operator_network_probes": list(operator_probes),
        "allowed_effect_domain_entrypoints": list(effect_entrypoints),
        "rules": {
            "decision_core_raw_network_forbidden": True,
            "application_business_logic_raw_network_forbidden": True,
            "admin_ui_raw_network_forbidden": True,
            "connectors_must_use_sealed_transport": True,
            "provider_endpoint_truth_lives_in_provider_transport_bindings": True,
            "operator_probes_are_local_server_only": True,
            "tests_are_not_allowed_as_production_bypass": True,
        },
    }


def register_network_side_effects_routes(*, router: APIRouter) -> None:
    @router.get(NETWORK_SIDE_EFFECTS_ROUTE, tags=["control-plane", "security"])
    async def control_plane_network_side_effects(
        tenant_id: str = "tenant-demo",
        business_id: str = "default-business",
    ) -> dict[str, Any]:
        return network_side_effects_payload(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_NETWORK_SIDE_EFFECTS_CONTROL_PLANE_ROUTES",
    "NETWORK_SIDE_EFFECTS_ROUTE",
    "network_side_effects_payload",
    "register_network_side_effects_routes",
]
