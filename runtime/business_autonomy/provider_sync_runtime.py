from __future__ import annotations

from dataclasses import dataclass

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderOperationPlan

CANON_PROVIDER_SYNC_RUNTIME = True

_READS = {
    'telegram_bot': ('message_read', 'contact_profile_read'),
    'whatsapp_cloud': ('message_read', 'contact_profile_read'),
    'email_connector': ('thread_sync', 'message_read'),
    'webflow': ('site_config_read',),
    'wordpress': ('site_config_read',),
    'shopify': ('catalog_sync', 'order_sync'),
    'woocommerce': ('catalog_sync', 'order_sync'),
    'amazon_marketplace': ('catalog_sync', 'order_sync'),
    'ebay_marketplace': ('catalog_sync', 'order_sync'),
    'etsy_marketplace': ('catalog_sync', 'order_sync'),
    'wildberries_marketplace': ('catalog_sync', 'order_sync'),
    'ozon_marketplace': ('catalog_sync', 'order_sync'),
    'hubspot': ('contact_sync', 'deal_sync'),
    'meta_ads': ('campaign_report_read',),
    'google_ads': ('campaign_report_read',),
    'tiktok_ads': ('campaign_report_read',),
}

_WRITES = {
    'telegram_bot': ('message_send',),
    'whatsapp_cloud': ('message_send', 'template_send'),
    'email_connector': ('message_send', 'campaign_send'),
    'sms_connector': ('message_send',),
    'webflow': ('page_publish', 'cms_item_publish'),
    'wordpress': ('page_publish', 'post_publish'),
    'shopify': ('platform_listing_write', 'refund_request'),
    'woocommerce': ('product_publish', 'refund_request'),
    'amazon_marketplace': ('platform_listing_write', 'shipment_update'),
    'ebay_marketplace': ('platform_listing_write', 'fulfillment_update'),
    'etsy_marketplace': ('platform_listing_write',),
    'wildberries_marketplace': ('platform_listing_write', 'stock_update'),
    'ozon_marketplace': ('platform_listing_write', 'stock_update'),
    'hubspot': ('task_create', 'contact_upsert'),
    'meta_ads': ('campaign_launch', 'campaign_pause', 'campaign_budget_update'),
    'google_ads': ('campaign_launch', 'campaign_pause', 'campaign_budget_update'),
    'tiktok_ads': ('campaign_launch', 'campaign_pause', 'campaign_budget_update'),
    'postgres_runtime': ('write_runtime_record',),
    'redis_runtime': ('write_runtime_key',),
    'clickhouse_export': ('export_analytics_batch',),
}


@dataclass(frozen=True)
class ProviderSyncRuntimePlanner:
    def describe(self, provider: ProviderDefinition) -> ProviderOperationPlan:
        reads = tuple(_READS.get(provider.provider_key, ()))
        writes = tuple(_WRITES.get(provider.provider_key, (provider.default_action_type,)))
        ops = tuple(dict.fromkeys((*reads, *writes)).keys())
        return ProviderOperationPlan(
            provider_key=provider.provider_key,
            operations=ops,
            read_operations=reads,
            write_operations=writes,
            webhook_enabled=provider.domain in {'communications', 'website', 'commerce'},
            metadata={
                'adapter_key': provider.adapter_key,
                'domain': provider.domain,
                'supports_business_onboarding': bool(provider.supports_business_onboarding),
            },
        )


__all__ = ['CANON_PROVIDER_SYNC_RUNTIME', 'ProviderSyncRuntimePlanner']
