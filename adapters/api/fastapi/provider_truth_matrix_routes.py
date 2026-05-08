from __future__ import annotations

"""Control-plane route registrar for the canonical provider truth matrix.

The route is intentionally read-only and delegates all provider status truth to
application.business_autonomy.provider_truth_matrix.  It must not grow a second
registry, connector catalog, or endpoint-readiness decision path.
"""

from typing import Any

from fastapi import APIRouter

from application.business_autonomy.provider_truth_matrix import (
    list_provider_truth_payloads,
    summarize_provider_truth,
)

CANON_PROVIDER_TRUTH_MATRIX_CONTROL_PLANE_ROUTES = True
PROVIDER_TRUTH_MATRIX_ROUTE = "/control-plane/provider-admin/truth-matrix"


def provider_truth_matrix_payload(*, tenant_id: str, business_id: str = "default-business") -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    business = str(business_id or "default-business").strip() or "default-business"
    rows = list_provider_truth_payloads()
    summary = summarize_provider_truth()
    return {
        "tenant_id": tenant,
        "business_id": business,
        "read_only": True,
        "status": "ok",
        "surface": "control_plane",
        "source": "application.business_autonomy.provider_truth_matrix",
        "live_ready_policy": summary["live_ready_policy"],
        "summary": summary,
        "rows": rows,
        "rules": {
            "provider_in_catalog_is_not_implemented": True,
            "endpoint_is_not_live_ready": True,
            "placeholder_endpoint_is_never_live_ready": True,
            "runtime_write_operation_is_not_write_supported": True,
            "telegram_bot_is_not_telegram_ads": True,
            "google_maps_inquiry_is_not_google_business_write": True,
            "write_requires_approval_budget_risk_verification_evidence": True,
        },
    }


def register_provider_truth_matrix_routes(*, router: APIRouter) -> None:
    @router.get(PROVIDER_TRUTH_MATRIX_ROUTE, tags=["control-plane", "providers"])
    async def control_plane_provider_truth_matrix(
        tenant_id: str = "tenant-demo",
        business_id: str = "default-business",
    ) -> dict[str, Any]:
        return provider_truth_matrix_payload(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_PROVIDER_TRUTH_MATRIX_CONTROL_PLANE_ROUTES",
    "PROVIDER_TRUTH_MATRIX_ROUTE",
    "provider_truth_matrix_payload",
    "register_provider_truth_matrix_routes",
]
