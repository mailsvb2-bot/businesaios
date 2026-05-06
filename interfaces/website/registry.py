"""Honest website connector registry.

SiteConnector remains the only named website contour. It now publishes a
capability-aware registry entry instead of a flat implemented/not_implemented
status.
"""

from interfaces.common.registry_capability_contract import build_registry_entry

CONNECTORS = {
    "site": build_registry_entry(
        name="site",
        status="implemented",
        read=True,
        write=False,
        verify=False,
        supports_dry_run=False,
        supports_idempotency=False,
        production_ready=False,
        action_types=("create_landing_page", "publish_service_page"),
    ),
    "analytics": build_registry_entry(name="analytics", status="not_implemented"),
    "cms_shopify": build_registry_entry(name="cms_shopify", status="not_implemented"),
    "cms_webflow": build_registry_entry(name="cms_webflow", status="not_implemented"),
    "cms_wordpress": build_registry_entry(name="cms_wordpress", status="not_implemented"),
    "form_events": build_registry_entry(name="form_events", status="not_implemented"),
}

__all__ = ["CONNECTORS"]
