from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from runtime.settings.event_store_gateway import build_event_store_settings_gateway


def build_messaging_settings_gateway(*, event_store):
    return build_event_store_settings_gateway(event_store=event_store)
