from __future__ import annotations

from runtime.settings.event_store_gateway import build_event_store_settings_gateway

CANON_BOOT_WIRING_ONLY = True

def build_messaging_settings_gateway(*, event_store):
    return build_event_store_settings_gateway(event_store=event_store)
