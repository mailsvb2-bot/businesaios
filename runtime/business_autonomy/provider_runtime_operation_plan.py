from __future__ import annotations

from application.business_autonomy.provider_runtime_contract import ProviderOperationPlan


def build_provider_runtime_operation_plan(provider) -> ProviderOperationPlan:
    operations = tuple(getattr(provider, 'operations', ()) or ())
    read_ops = tuple(op for op in operations if 'sync' in op or op.endswith('_read') or op in {'order_sync', 'contact_sync', 'contacts_sync', 'catalog_sync'})
    write_ops = tuple(op for op in operations if op not in read_ops)
    return ProviderOperationPlan(
        provider_key=getattr(provider, 'provider_key', ''),
        operations=operations,
        read_operations=read_ops,
        write_operations=write_ops,
        webhook_enabled=bool(getattr(provider, 'webhook_headers', {})) or getattr(provider, 'provider_key', '') in {'shopify', 'telegram_bot', 'generic_website'},
        metadata={'domain': getattr(provider, 'domain', '')},
    )
