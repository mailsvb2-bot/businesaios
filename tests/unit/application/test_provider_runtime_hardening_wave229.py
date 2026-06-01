from __future__ import annotations

import base64
import hashlib
import hmac

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.bootstrap import (
    StaticGovernanceEnablement,
    StaticPersistenceSurface,
    _build_typed_channel_registry,
)
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_runtime_audit import ProviderRuntimeAuditRecorder
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


class _FailingTransport:
    def execute(self, **_: object):
        raise TimeoutError('provider timed out')


def _service(tmp_path):
    documents = FileDistributedDocumentStore(tmp_path / 'docs')
    registry = DistributedBusinessRegistry(documents=documents)
    onboarding = ConnectorOnboardingService(
        adapter_registry=_build_typed_channel_registry(),
        business_registry=registry,
        trust_onboarding=StaticTrustOnboarding(),
        governance_enablement=StaticGovernanceEnablement(),
        persistence_surface=StaticPersistenceSurface(),
    )
    return ProviderAdminService(
        onboarding_service=onboarding,
        secret_vault=InMemorySecretVault(),
        connector_secret_scope=ConnectorSecretScope(),
        activation_store=FileProviderActivationStore(documents),
        route_state=FileRegionRouteState(documents),
    )


def test_provider_live_sync_records_audit_refs_on_failure(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='shop-a',
            provider_key='shopify',
            ownership_key='owner:shop-a',
            requested_by='owner-user',
            external_ref='shop://a',
            secrets={'admin_access_token': 'shpat_test', 'webhook_secret': 'whsec'},
            metadata={'probe_mode': 'dry_run'},
        )
    )
    provider = provider_map()['shopify']
    audit = ProviderRuntimeAuditRecorder.in_memory()
    result = ProviderLiveSyncRuntime(
        service.secret_vault,
        transports={'shopify': _FailingTransport()},
        audit_recorder=audit,
    ).run(
        provider=provider,
        tenant_id='tenant-a',
        business_id='shop-a',
        operation='catalog_sync',
        mode='live',
        payload={'cursor': '1'},
    )
    assert result.status == 'live_execution_failed'
    assert result.accepted is False
    assert dict(result.metadata).get('error', {}).get('category') == 'transport_timeout'
    refs = dict(result.metadata).get('audit_refs', {})
    assert refs.get('audit_event_id')
    assert refs.get('evidence_id')


def test_inbound_webhook_service_rejects_replay_and_records_refs(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='shop-a',
            provider_key='shopify',
            ownership_key='owner:shop-a',
            requested_by='owner-user',
            external_ref='shop://a',
            secrets={'admin_access_token': 'shpat_test', 'webhook_secret': 'whsec'},
            metadata={'probe_mode': 'dry_run'},
        )
    )
    provider = provider_map()['shopify']
    runtime = ProviderWebhookRuntime(service.secret_vault)
    body = b'{"id": 1}'
    signature = base64.b64encode(hmac.new(b'whsec', body, hashlib.sha256).digest()).decode('ascii')
    inbound = ProviderInboundWebhookService(
        webhook_runtime=runtime,
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        audit_recorder=ProviderRuntimeAuditRecorder.in_memory(),
    )
    first = inbound.ingest(
        provider=provider,
        tenant_id='tenant-a',
        business_id='shop-a',
        headers={'X-Shopify-Hmac-Sha256': signature},
        body=body,
        event_key='evt-1',
        topic='orders/create',
    )
    second = inbound.ingest(
        provider=provider,
        tenant_id='tenant-a',
        business_id='shop-a',
        headers={'X-Shopify-Hmac-Sha256': signature},
        body=body,
        event_key='evt-1',
        topic='orders/create',
    )
    assert first.accepted is True
    assert second.accepted is False
    assert second.status == 'replayed'
    assert dict(second.metadata).get('audit_refs', {}).get('audit_event_id')


def test_provider_admin_service_can_revoke_and_reconnect(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='shop-a',
            provider_key='shopify',
            ownership_key='owner:shop-a',
            requested_by='owner-user',
            external_ref='shop://a',
            secrets={'admin_access_token': 'shpat_test', 'webhook_secret': 'whsec'},
            metadata={'probe_mode': 'dry_run'},
        )
    )
    revoked = service.revoke_provider(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify')
    assert revoked.connected is False
    assert dict(revoked.metadata).get('secret_lifecycle', {}).get('last_action') == 'revoked'
    reconnected = service.reconnect_provider(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', probe_mode='dry_run')
    assert reconnected.connected is False
    assert dict(reconnected.metadata).get('secret_lifecycle', {}).get('last_action') == 'reconnected'
    assert dict(reconnected.metadata).get('health_probe', {}).get('status') in {'missing_required_secrets', 'misconfigured'}
