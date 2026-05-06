from application.business_autonomy.provider_catalog import PROVIDERS
from runtime.business_autonomy.bootstrap import _build_typed_channel_registry
from application.business_autonomy.channel_contracts import ChannelIdentity


def test_provider_catalog_business_onboarding_adapters_are_registered():
    registry = _build_typed_channel_registry()
    for provider in PROVIDERS:
        if not provider.supports_business_onboarding:
            continue
        identity = ChannelIdentity(
            business_id='b1',
            tenant_id='tenant-test',
            channel_kind=provider.channel_kind,
            adapter_key=provider.adapter_key,
            external_ref=f'{provider.provider_key}://external',
            region=provider.default_region,
        )
        resolved = registry.resolve(identity)
        capabilities = resolved.adapter.discover_capabilities(identity=identity)
        assert resolved.identity.adapter_key == provider.adapter_key
        assert capabilities
