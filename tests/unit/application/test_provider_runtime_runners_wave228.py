from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from reliability.idempotency_store import InMemoryIdempotencyStore
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put_secret(vault: InMemorySecretVault, *, tenant_id: str, connector_id: str, business_id: str, secret_name: str, value: str) -> None:
    ref = SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR, metadata={}), plaintext=value.encode('utf-8'))


def test_webhook_replay_guard_rejects_duplicate_shopify_event():
    provider = provider_map()['shopify']
    guard = ProviderWebhookReplayGuard(InMemoryIdempotencyStore())
    first = guard.reserve_event(provider=provider, tenant_id='tenant-a', business_id='shop-a', event_key='evt-1', payload_digest='sha256:abc', topic='orders/create')
    second = guard.reserve_event(provider=provider, tenant_id='tenant-a', business_id='shop-a', event_key='evt-1', payload_digest='sha256:abc', topic='orders/create')
    assert first.accepted is True
    assert second.accepted is False
    assert second.resolution in {'rejected_in_progress', 'replay_completed'}


def test_live_sync_runtime_is_dry_run_ready_but_fail_closed_without_transport():
    vault = InMemorySecretVault()
    provider = provider_map()['shopify']
    _put_secret(vault, tenant_id='tenant-a', connector_id=provider.connector_id, business_id='shop-a', secret_name=f'{provider.connector_id}.admin_access_token', value='shpat_demo')
    _put_secret(vault, tenant_id='tenant-a', connector_id=provider.connector_id, business_id='shop-a', secret_name=f'{provider.connector_id}.webhook_secret', value='whsec_demo')
    runtime = ProviderLiveSyncRuntime(vault)
    dry = runtime.run(provider=provider, tenant_id='tenant-a', business_id='shop-a', operation='order_sync', mode='dry_run', payload={'since': '2026-01-01'})
    live = runtime.run(provider=provider, tenant_id='tenant-a', business_id='shop-a', operation='order_sync', mode='live', payload={'since': '2026-01-01'})
    assert dry.accepted is True
    assert dry.status == 'dry_run_ready'
    assert live.accepted is False
    assert live.status == 'live_transport_unbound'


def test_provider_admin_status_contains_live_runner_and_replay_guard(tmp_path):
    from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
    from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
    from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
    from application.business_autonomy.provider_admin_service import ProviderAdminService
    from runtime.business_autonomy.bootstrap import StaticGovernanceEnablement, StaticPersistenceSurface, _build_typed_channel_registry
    from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
    from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
    from security.connector_secret_scope import ConnectorSecretScope

    documents = FileDistributedDocumentStore(tmp_path / 'docs')
    registry = DistributedBusinessRegistry(documents=documents)
    onboarding = ConnectorOnboardingService(
        adapter_registry=_build_typed_channel_registry(),
        business_registry=registry,
        trust_onboarding=StaticTrustOnboarding(),
        governance_enablement=StaticGovernanceEnablement(),
        persistence_surface=StaticPersistenceSurface(),
    )
    service = ProviderAdminService(
        onboarding_service=onboarding,
        secret_vault=InMemorySecretVault(),
        connector_secret_scope=ConnectorSecretScope(),
        activation_store=FileProviderActivationStore(documents),
        route_state=FileRegionRouteState(documents),
    )
    status = service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='shop-a',
            provider_key='shopify',
            ownership_key='owner:shop-a',
            requested_by='owner-user',
            external_ref='shopify://shop-a',
            secrets={'admin_access_token': 'shpat_demo', 'webhook_secret': 'whsec_demo'},
            metadata={'probe_mode': 'dry_run'},
        )
    )
    assert dict(status.metadata.get('live_sync_runner') or {}).get('dry_run_supported') is True
    assert dict(status.metadata.get('webhook_replay_guard') or {}).get('enabled') is True
