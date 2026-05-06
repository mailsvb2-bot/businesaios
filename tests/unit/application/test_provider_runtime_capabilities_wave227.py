from __future__ import annotations

import base64
import hashlib
import hmac

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.bootstrap import StaticGovernanceEnablement, StaticPersistenceSurface, _build_typed_channel_registry
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


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


def test_shopify_activation_emits_health_webhook_and_runtime_plan(tmp_path):
    service = _service(tmp_path)
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
    health = dict(status.metadata.get('health_probe') or {})
    webhook = dict(status.metadata.get('webhook_contract') or {})
    runtime_plan = dict(status.metadata.get('runtime_plan') or {})
    assert health.get('status') == 'ready_for_credentials'
    assert webhook.get('enabled') is True
    assert webhook.get('verification_kind') == 'hmac_sha256_base64'
    assert 'platform_listing_write' in tuple(runtime_plan.get('write_operations') or ())
    assert 'order_sync' in tuple(runtime_plan.get('read_operations') or ())


def test_shopify_webhook_verification_uses_secret_vault(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
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
    provider = provider_map()['shopify']
    runtime = ProviderWebhookRuntime(service.secret_vault)
    body = b'{"topic":"orders/create"}'
    signature = base64.b64encode(hmac.new(b'whsec_demo', body, hashlib.sha256).digest()).decode('ascii')
    assert runtime.verify(
        provider=provider,
        tenant_id='tenant-a',
        business_id='shop-a',
        headers={'X-Shopify-Hmac-Sha256': signature},
        body=body,
    ) is True
