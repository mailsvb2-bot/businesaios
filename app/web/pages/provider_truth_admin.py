from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.business_autonomy.provider_truth_matrix import list_provider_truth_payloads, summarize_provider_truth
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_PROVIDER_TRUTH_ADMIN_PAGE = True


@dataclass(frozen=True, slots=True)
class ProviderTruthAdminPage:
    """Admin-visible provider truth matrix surface.

    This is a read-only control-plane/admin surface for provider readiness truth.
    It intentionally separates live/read/write truth from optimistic catalog,
    connector, transport or manifest presence.
    """

    kind: str = "provider_truth_admin_page"

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get("tenant_id"))
        business_id = str(normalized.get("business_id") or "default-business").strip() or "default-business"
        rows = list_provider_truth_payloads()
        summary = summarize_provider_truth()
        return build_kinded_payload(
            self.kind,
            {
                "tenant_id": tenant_id,
                "business_id": business_id,
                "title": "Provider Truth Matrix",
                "subtitle": "Единая правда о провайдерах: catalog/manifest/endpoint не равны production readiness.",
                "read_only": True,
                "live_ready_policy": summary["live_ready_policy"],
                "summary": summary,
                "rows": rows,
                "rules": {
                    "example_invalid_is_never_live_ready": True,
                    "manifest_presence_is_not_implementation": True,
                    "runtime_write_operation_is_not_write_supported": True,
                    "telegram_bot_is_not_telegram_ads": True,
                    "google_maps_inquiry_is_not_google_business_write": True,
                    "external_write_requires_approval_budget_risk_verification_evidence": True,
                },
                "actions": {
                    "provider_catalog_endpoint": "/control-plane/provider-admin/catalog",
                    "provider_runtime_routes_endpoint": "/control-plane/provider-runtime/routes",
                    "provider_tokens_admin_path": "/web/provider-tokens",
                    "connector_admin_path": "/web/connector-admin",
                },
                "tenant_bound": True,
            },
        )


__all__ = ["CANON_WEB_PROVIDER_TRUTH_ADMIN_PAGE", "ProviderTruthAdminPage"]
