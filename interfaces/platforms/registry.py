"""Honest marketplace-platform connector registry.

Google Maps is the only named platform contour still carried as an implemented
surface. It is capability-aware and remains non-production until verified write
and evidence paths exist.
"""

from interfaces.common.registry_capability_contract import build_registry_entry

CONNECTORS = {
    "google_maps": build_registry_entry(
        name="google_maps",
        status="implemented",
        read=True,
        write=False,
        verify=False,
        supports_dry_run=False,
        supports_idempotency=False,
        production_ready=False,
        action_types=(),
    ),
    "amazon": build_registry_entry(name="amazon", status="not_implemented"),
    "avito": build_registry_entry(name="avito", status="not_implemented"),
    "craigslist": build_registry_entry(name="craigslist", status="not_implemented"),
    "etsy": build_registry_entry(name="etsy", status="not_implemented"),
    "fiverr": build_registry_entry(name="fiverr", status="not_implemented"),
    "upwork": build_registry_entry(name="upwork", status="not_implemented"),
    "yelp": build_registry_entry(name="yelp", status="not_implemented"),
}

__all__ = ["CONNECTORS"]
