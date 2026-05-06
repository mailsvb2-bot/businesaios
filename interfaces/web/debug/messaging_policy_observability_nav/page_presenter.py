from __future__ import annotations

from dataclasses import dataclass

from interfaces.web.debug.common.query_utils import clean_text


@dataclass(frozen=True)
class NavItem:
    key: str
    title: str
    path: str
    description: str


@dataclass(frozen=True)
class NavViewItem:
    key: str
    title: str
    path: str
    description: str
    href: str


@dataclass(frozen=True)
class MessagingPolicyObservabilityNavPageModel:
    tenant_id: str
    items: tuple[NavViewItem, ...]


def default_tenant_id(value) -> str:
    return clean_text(value, default='default')


def all_nav_items() -> tuple[NavItem, ...]:
    return (
        NavItem('snapshot', 'Snapshot', '/debug/messaging-policy-snapshot', 'Inspect one messaging policy snapshot by tenant, user and correlation id.'),
        NavItem('traces', 'Traces', '/debug/messaging-policy-traces', 'Search recent messaging policy traces in a time window.'),
        NavItem('dashboard', 'Dashboard', '/debug/messaging-policy-dashboard', 'Aggregate delivery outcomes, rates and channel distributions.'),
        NavItem('alerts', 'Alerts', '/debug/messaging-policy-alerts', 'Show anomaly detection findings for messaging policy observability.'),
        NavItem('alert_subscriptions', 'Alert subscriptions', '/settings/alert-subscriptions', 'Manage alert notification subscriptions and channels.'),
    )


def _build_link(*, base_path: str, tenant_id: str) -> str:
    return f"{str(base_path)}?tenant_id={str(tenant_id)}"


def _present_nav_item(item: NavItem, *, tenant_id: str) -> NavViewItem:
    return NavViewItem(
        key=item.key,
        title=item.title,
        path=item.path,
        description=item.description,
        href=_build_link(base_path=item.path, tenant_id=str(tenant_id)),
    )


def page_to_dict(model: MessagingPolicyObservabilityNavPageModel) -> dict:
    return {
        'tenant_id': model.tenant_id,
        'items': [
            {
                'key': item.key,
                'title': item.title,
                'path': item.path,
                'description': item.description,
                'href': item.href,
            }
            for item in model.items
        ],
    }


def present_page(*, tenant_id) -> MessagingPolicyObservabilityNavPageModel:
    tenant = default_tenant_id(tenant_id)
    return MessagingPolicyObservabilityNavPageModel(
        tenant_id=tenant,
        items=tuple(_present_nav_item(item, tenant_id=tenant) for item in all_nav_items()),
    )
