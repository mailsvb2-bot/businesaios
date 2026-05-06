from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind

CANON_COMMERCE_PRODUCTION_ADAPTERS = True


class WooCommerceProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = 'commerce.woocommerce'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('woocommerce.catalog', ('catalog_sync', 'product_publish'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('woocommerce.orders', ('order_sync', 'refund_request'), write_enabled=True, human_verification_required=True),
        ),
    )


class AmazonMarketplaceProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = 'commerce.amazon_marketplace'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('amazon.listings', ('platform_listing_write', 'catalog_sync'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('amazon.orders', ('order_sync', 'shipment_update'), write_enabled=True, human_verification_required=True),
        ),
    )


class EbayMarketplaceProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = 'commerce.ebay_marketplace'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('ebay.listings', ('platform_listing_write', 'catalog_sync'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('ebay.orders', ('order_sync', 'fulfillment_update'), write_enabled=True, human_verification_required=True),
        ),
    )


class EtsyMarketplaceProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = 'commerce.etsy_marketplace'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('etsy.catalog', ('platform_listing_write', 'catalog_sync'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('etsy.orders', ('order_sync',), write_enabled=True, human_verification_required=True),
        ),
    )


class WildberriesMarketplaceProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = 'commerce.wildberries_marketplace'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('wildberries.catalog', ('platform_listing_write', 'catalog_sync'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('wildberries.orders', ('order_sync', 'stock_update'), write_enabled=True, human_verification_required=True),
        ),
    )


class OzonMarketplaceProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = 'commerce.ozon_marketplace'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('ozon.catalog', ('platform_listing_write', 'catalog_sync'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('ozon.orders', ('order_sync', 'stock_update'), write_enabled=True, human_verification_required=True),
        ),
    )
