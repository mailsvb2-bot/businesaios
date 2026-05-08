from __future__ import annotations

from fastapi import APIRouter

from adapters.api.fastapi.provider_truth_matrix_routes import (
    PROVIDER_TRUTH_MATRIX_ROUTE,
    provider_truth_matrix_payload,
    register_provider_truth_matrix_routes,
)
from application.business_autonomy.provider_catalog import PROVIDERS


def test_provider_truth_matrix_payload_is_read_only_control_plane_surface() -> None:
    payload = provider_truth_matrix_payload(tenant_id="tenant-demo", business_id="business-demo")

    assert payload["tenant_id"] == "tenant-demo"
    assert payload["business_id"] == "business-demo"
    assert payload["read_only"] is True
    assert payload["surface"] == "control_plane"
    assert payload["source"] == "application.business_autonomy.provider_truth_matrix"
    assert "read_only_advisory" in payload["live_ready_policy"]
    assert payload["summary"]["total"] == len(PROVIDERS)
    assert payload["summary"]["write_supported"] == 0
    assert payload["summary"]["live_ready"] == 0
    assert payload["rows"]


def test_provider_truth_matrix_payload_contains_required_provider_truth_fields() -> None:
    payload = provider_truth_matrix_payload(tenant_id="tenant-demo")
    required = {
        "provider_key",
        "category",
        "display_name",
        "auth_scheme",
        "required_credentials",
        "read_capabilities",
        "write_capabilities",
        "status",
        "live_ready",
        "read_only_supported",
        "write_supported",
        "approval_required",
        "has_real_endpoint",
        "has_placeholder_endpoint",
        "endpoint_source",
        "health_requirements",
        "admin_visible",
        "owner",
        "risk_level",
    }
    for row in payload["rows"]:
        assert required.issubset(row.keys())


def test_provider_truth_matrix_route_is_registered_once() -> None:
    router = APIRouter()
    register_provider_truth_matrix_routes(router=router)
    routes = [getattr(route, "path", "") for route in router.routes]
    assert routes.count(PROVIDER_TRUTH_MATRIX_ROUTE) == 1


def test_provider_truth_matrix_rules_prevent_provider_claim_drift() -> None:
    payload = provider_truth_matrix_payload(tenant_id="tenant-demo")
    rules = payload["rules"]
    assert rules["provider_in_catalog_is_not_implemented"] is True
    assert rules["endpoint_is_not_live_ready"] is True
    assert rules["placeholder_endpoint_is_never_live_ready"] is True
    assert rules["runtime_write_operation_is_not_write_supported"] is True
    assert rules["telegram_bot_is_not_telegram_ads"] is True
    assert rules["google_maps_inquiry_is_not_google_business_write"] is True
    assert rules["write_requires_approval_budget_risk_verification_evidence"] is True


def test_ads_remain_not_live_write_ready_in_control_plane_payload() -> None:
    payload = provider_truth_matrix_payload(tenant_id="tenant-demo")
    rows = {row["provider_key"]: row for row in payload["rows"]}
    for provider_key in ("google_ads", "meta_ads", "tiktok_ads"):
        row = rows[provider_key]
        assert row["category"] == "ads"
        assert row["risk_level"] == "high"
        assert row["write_supported"] is False
        assert row["live_ready"] is False
        assert row["approval_required"] is True
