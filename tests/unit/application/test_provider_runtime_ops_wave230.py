from __future__ import annotations

import base64
import hashlib
import hmac

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.bootstrap import (
    StaticGovernanceEnablement,
    StaticPersistenceSurface,
    _build_typed_channel_registry,
)
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_runtime_observability import ProviderRuntimeObservability
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


class _TimeoutTransport:
    def execute(self, **_: object):
        raise TimeoutError('slow provider')


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


def test_rotate_provider_secrets_and_sync_retry_metadata(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='shop-a',
            provider_key='shopify',
            ownership_key='owner:shop-a',
            requested_by='owner-user',
            external_ref='shop://a',
            secrets={'admin_access_token': 'old-token', 'webhook_secret': 'whsec'},
            metadata={'probe_mode': 'dry_run'},
        )
    )
    rotated = service.rotate_provider_secrets(
        tenant_id='tenant-a',
        business_id='shop-a',
        provider_key='shopify',
        secrets={'admin_access_token': 'new-token'},
    )
    assert dict(rotated.metadata).get('secret_lifecycle', {}).get('last_action') == 'rotated'
    provider = provider_map()['shopify']
    observability = ProviderRuntimeObservability()
    runtime = ProviderLiveSyncRuntime(service.secret_vault, transports={'shopify': _TimeoutTransport()}, observability=observability)
    result = runtime.run(provider=provider, tenant_id='tenant-a', business_id='shop-a', operation='catalog_sync', mode='live')
    assert result.status == 'live_execution_failed'
    retry = dict(result.metadata).get('retry_policy', {})
    assert retry.get('retryable') is True
    assert int(retry.get('next_delay_seconds') or 0) > 0
    metric = observability.metrics_registry.metric_snapshot(tenant_id='tenant-a', metric_name='provider_runtime.sync_total')
    assert metric is not None


def test_ingest_provider_webhook_emits_acceptance_metric(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='shop-a',
            provider_key='shopify',
            ownership_key='owner:shop-a',
            requested_by='owner-user',
            external_ref='shop://a',
            secrets={'admin_access_token': 'token', 'webhook_secret': 'whsec'},
            metadata={'probe_mode': 'dry_run'},
        )
    )
    body = b'{"id": 11}'
    signature = base64.b64encode(hmac.new(b'whsec', body, hashlib.sha256).digest()).decode('ascii')
    payload = service.ingest_provider_webhook(
        tenant_id='tenant-a',
        business_id='shop-a',
        provider_key='shopify',
        headers={'X-Shopify-Hmac-Sha256': signature},
        body=body,
        event_key='evt-11',
        topic='orders/create',
    )
    assert payload['accepted'] is True
    assert payload['status'] == 'accepted'



def test_vk_native_callback_is_verified_and_returns_transport_ack(tmp_path) -> None:
    service = _service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(tenant_id='tenant-a', business_id='vk-a', provider_key='vk_messaging', ownership_key='owner:vk-a', requested_by='owner-user', external_ref='vk://123', secrets={'webhook_secret': 'vk-secret', 'confirmation_code': 'confirm-123'}, metadata={'probe_mode': 'dry_run'}))
    confirmation = b'{"type":"confirmation","group_id":123,"secret":"vk-secret"}'
    confirmed = service.ingest_provider_webhook(tenant_id='tenant-a', business_id='vk-a', provider_key='vk_messaging', headers={}, body=confirmation, event_key='', topic='')
    message = service.ingest_provider_webhook(tenant_id='tenant-a', business_id='vk-a', provider_key='vk_messaging', headers={}, body=b'{"type":"message_new","event_id":"evt-1","group_id":123,"secret":"vk-secret","object":{"message":{"id":9,"from_id":7,"peer_id":7,"text":"hello"}}}', event_key='', topic='')
    denied = service.ingest_provider_webhook(tenant_id='tenant-a', business_id='vk-a', provider_key='vk_messaging', headers={}, body=confirmation.replace(b'vk-secret', b'wrong'), event_key='', topic='')
    assert confirmed['status'] == 'accepted' and confirmed['response_body'] == 'confirm-123'
    assert message['status'] == 'accepted' and message['response_body'] == 'ok' and message['metadata']['route_extract']['topic'] == 'message_new'
    assert denied['status'] == 'invalid_signature' and denied['response_body'] is None


def test_secret_history_and_rollback(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='shop-a',
            provider_key='shopify',
            ownership_key='owner:shop-a',
            requested_by='owner-user',
            external_ref='shop://a',
            secrets={'admin_access_token': 'old-token', 'webhook_secret': 'whsec'},
            metadata={'probe_mode': 'dry_run'},
        )
    )
    service.rotate_provider_secrets(
        tenant_id='tenant-a',
        business_id='shop-a',
        provider_key='shopify',
        secrets={'admin_access_token': 'new-token'},
    )
    history = service.list_provider_secret_history(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify')
    assert any(item['secret_name'] == 'admin_access_token' and item['version'] != 'current' for item in history)
    version = next(item['version'] for item in history if item['secret_name'] == 'admin_access_token' and item['version'] != 'current')
    rolled = service.rollback_provider_secret_version(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', secret_name='admin_access_token', version=version)
    assert rolled['rollback']['restored_version'] == version
    assert rolled['status'].connected is True
