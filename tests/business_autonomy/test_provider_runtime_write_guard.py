from __future__ import annotations

from pathlib import Path

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
from runtime.business_autonomy.provider_runtime_write_guard import PROVIDER_WRITE_BLOCK_STATUS, ProviderRuntimeWriteGuard
from runtime.queue.job_store_sqlite import SqliteJobStore
from security.secret_vault import InMemorySecretVault


def test_write_guard_blocks_live_ads_write_without_truth_matrix_write_support() -> None:
    provider = provider_map()["google_ads"]
    decision = ProviderRuntimeWriteGuard().evaluate(provider=provider, operation="campaign_launch", mode="live")

    assert decision.allowed is False
    assert decision.status == PROVIDER_WRITE_BLOCK_STATUS
    assert decision.is_write_operation is True
    assert decision.reason == "write_supported_false_in_provider_truth_matrix"
    assert decision.metadata["truth_source"] == "application.business_autonomy.provider_truth_matrix"


def test_write_guard_allows_dry_run_write_preparation() -> None:
    provider = provider_map()["google_ads"]
    decision = ProviderRuntimeWriteGuard().evaluate(provider=provider, operation="campaign_launch", mode="dry_run")

    assert decision.allowed is True
    assert decision.status == "allowed_non_live_mode"
    assert decision.is_write_operation is True


def test_live_sync_runtime_blocks_live_write_before_health_or_transport_execution() -> None:
    provider = provider_map()["google_ads"]
    runtime = ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={})

    result = runtime.run(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="live",
        payload={"budget": 100},
    )

    assert result.accepted is False
    assert result.status == PROVIDER_WRITE_BLOCK_STATUS
    guard = result.metadata["provider_write_guard"]
    assert guard["allowed"] is False
    assert guard["is_write_operation"] is True
    assert guard["metadata"]["truth"]["write_supported"] is False
    assert "health_probe" not in result.metadata
    assert "transport_response" not in result.metadata


def test_live_sync_runtime_still_allows_dry_run_write_envelope() -> None:
    provider = provider_map()["google_ads"]
    runtime = ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={})

    result = runtime.run(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="dry_run",
        payload={"budget": 100},
    )

    assert result.accepted is False or result.status in {"dry_run_ready", "rejected_misconfigured"}
    assert result.metadata["provider_write_guard"]["status"] == "allowed_non_live_mode"


def test_queue_blocks_live_write_job_before_persistence(tmp_path: Path) -> None:
    provider = provider_map()["google_ads"]
    store = SqliteJobStore(tmp_path / "provider_jobs.sqlite3")
    queue = ProviderQueueExecutionRuntime(
        secret_vault=InMemorySecretVault(),
        live_runtime=ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={}),
        store=store,
    )

    result = queue.enqueue_sync(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="live",
        payload={"budget": 100},
    )

    assert result.queued is False
    assert result.job_id == ""
    assert result.status == PROVIDER_WRITE_BLOCK_STATUS
    assert result.metadata["fail_closed_before_queue"] is True
    assert result.metadata["provider_write_guard"]["allowed"] is False
    assert queue.list_jobs(tenant_id="tenant-demo", business_id="business-demo", provider_key="google_ads") == ()


def test_queue_allows_dry_run_write_job() -> None:
    provider = provider_map()["google_ads"]
    queue = ProviderQueueExecutionRuntime(
        secret_vault=InMemorySecretVault(),
        live_runtime=ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={}),
    )

    result = queue.enqueue_sync(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="dry_run",
        payload={"budget": 100},
    )

    assert result.queued is True
    assert result.status == "queued"
    assert result.metadata["provider_write_guard"]["status"] == "allowed_non_live_mode"
