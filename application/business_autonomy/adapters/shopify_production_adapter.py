from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelExecutionEnvelope, ChannelIdentity, ChannelKind
from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult, ExecutionVerdict

CANON_SHOPIFY_PRODUCTION_ADAPTER = True


@dataclass(frozen=True)
class ShopifyCredentials:
    shop_domain: str
    admin_access_token: str
    webhook_secret: str | None = None

    def validate(self) -> None:
        if '.myshopify.com' not in str(self.shop_domain or ''):
            raise ValueError('shop_domain must be a myshopify domain')
        if not str(self.admin_access_token or '').strip():
            raise ValueError('admin_access_token is required')


class ShopifyProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = 'commerce.shopify'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('shopify.catalog', ('catalog_sync', 'product_publish'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('shopify.orders', ('order_sync', 'refund_request', 'fulfillment_update'), write_enabled=True, human_verification_required=True),
        ),
    )

    def discover_capabilities(self, *, identity: ChannelIdentity) -> Sequence[ChannelCapabilityDescriptor]:
        capabilities = super().discover_capabilities(identity=identity)
        return tuple(capabilities)

    async def execute(self, *, envelope: ChannelExecutionEnvelope, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        result = await super().execute(envelope=envelope, request=request)
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.SIMULATED if request.envelope.simulation else ExecutionVerdict.COMPLETED,
            business_id=result.business_id,
            goal_id=result.goal_id,
            execution_id=result.execution_id,
            message='shopify production adapter accepted commerce envelope',
            metrics={**dict(result.metrics or {}), 'transport': 'shopify_admin_api'},
            evidence=result.evidence,
            delegated_to_domain_engine=True,
            adapter_name=self.adapter_key,
            metadata={**dict(result.metadata or {}), 'provider': 'shopify'},
        )

    def credential_contract(self) -> dict[str, str]:
        return {
            'shop_domain': 'store domain ending in .myshopify.com',
            'admin_access_token': 'private app or custom app admin token',
            'webhook_secret': 'optional webhook signing secret',
        }
