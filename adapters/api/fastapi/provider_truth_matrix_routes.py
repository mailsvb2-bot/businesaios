from __future__ import annotations

from typing import Any

from adapters.api.fastapi.router_support import authorize_request, require_platform_scope

from fastapi import APIRouter, Request

from application.business_autonomy.provider_truth_matrix import list_provider_truth_payloads, summarize_provider_truth

CANON_PROVIDER_TRUTH_MATRIX_CONTROL_PLANE_ROUTES = True
PROVIDER_TRUTH_MATRIX_ROUTE = "/control-plane/provider-admin/truth-matrix"
_RULES = {
    "provider_in_catalog_is_not_implemented": True, "endpoint_is_not_live_ready": True,
    "placeholder_endpoint_is_never_live_ready": True, "runtime_write_requires_explicit_guard_allowlist": True,
    "telegram_bot_is_not_telegram_ads": True, "google_maps_inquiry_is_not_google_business_write": True,
    "write_requires_approval_budget_risk_verification_evidence": True,
}


def provider_truth_matrix_payload(*, tenant_id: str, business_id: str = "default-business") -> dict[str, Any]:
    summary = summarize_provider_truth()
    return {
        "tenant_id": str(tenant_id or "").strip(), "business_id": str(business_id or "default-business").strip() or "default-business",
        "read_only": True, "status": "ok", "surface": "control_plane",
        "source": "application.business_autonomy.provider_truth_matrix", "live_ready_policy": summary["live_ready_policy"],
        "summary": summary, "rows": list_provider_truth_payloads(), "rules": dict(_RULES),
    }


def register_provider_truth_matrix_routes(*, router: APIRouter, auth_bundle) -> None:
    @router.get(PROVIDER_TRUTH_MATRIX_ROUTE, tags=["control-plane", "providers"])
    async def control_plane_provider_truth_matrix(request: Request, tenant_id: str = "tenant-demo", business_id: str = "default-business") -> dict[str, Any]:
        _, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        require_platform_scope(principal)
        if str(principal.tenant_id) != str(tenant_id) and str(tenant_id) != 'tenant-demo':
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail='tenant_scope_mismatch')
        return provider_truth_matrix_payload(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_PROVIDER_TRUTH_MATRIX_CONTROL_PLANE_ROUTES", "PROVIDER_TRUTH_MATRIX_ROUTE", "provider_truth_matrix_payload", "register_provider_truth_matrix_routes"]
