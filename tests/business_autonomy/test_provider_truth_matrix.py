from __future__ import annotations

from application.business_autonomy.provider_catalog import PROVIDERS
from application.business_autonomy.provider_truth_matrix import (
    build_provider_truth_matrix,
    provider_truth_map,
    summarize_provider_truth,
)
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings


def test_provider_truth_matrix_covers_every_catalog_provider() -> None:
    expected = {item.provider_key for item in PROVIDERS}
    actual = {row.provider_key for row in build_provider_truth_matrix()}
    assert actual == expected


def test_placeholder_endpoints_are_never_live_ready() -> None:
    for row in build_provider_truth_matrix():
        if row.has_placeholder_endpoint:
            assert row.live_ready is False
            assert row.status != "live_ready"


def test_transport_live_ready_does_not_create_external_write_support() -> None:
    truth = provider_truth_map()
    bindings = ProviderTransportBindings()
    for provider in PROVIDERS:
        binding = bindings.describe(provider)
        if binding.get("live_ready") and provider.domain in {"ads", "marketplace", "communications", "commerce"}:
            row = truth[provider.provider_key]
            assert row.write_supported is False
            assert row.live_ready is False
            assert row.approval_required is True


def test_runtime_write_operations_are_not_reported_as_write_supported_without_guard_contract() -> None:
    planner = ProviderSyncRuntimePlanner()
    truth = provider_truth_map()
    providers_with_runtime_writes = {
        provider.provider_key
        for provider in PROVIDERS
        if planner.describe(provider).write_operations
    }
    assert providers_with_runtime_writes
    for provider_key in providers_with_runtime_writes:
        row = truth[provider_key]
        assert row.write_capabilities
        assert row.write_supported is False


def test_ads_are_read_only_or_contract_not_live_write_ready() -> None:
    truth = provider_truth_map()
    for provider_key in ("google_ads", "meta_ads", "tiktok_ads"):
        row = truth[provider_key]
        assert row.category == "ads"
        assert row.risk_level == "high"
        assert row.write_supported is False
        assert row.live_ready is False
        assert row.approval_required is True


def test_telegram_bot_is_not_telegram_ads() -> None:
    truth = provider_truth_map()
    assert "telegram_bot" in truth
    assert "telegram_ads" not in truth
    assert truth["telegram_bot"].category == "communications"


def test_matrix_summary_is_admin_safe_read_only_pilot() -> None:
    summary = summarize_provider_truth()
    assert summary["total"] == len(PROVIDERS)
    assert summary["write_supported"] == 0
    assert summary["live_ready"] == 0
    assert "read_only_advisory" in summary["live_ready_policy"]
    assert summary["admin_visible"] == len(PROVIDERS)
