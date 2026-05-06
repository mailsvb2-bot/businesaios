from __future__ import annotations


class EventStoreSettingsWriter:

    def __init__(self, *, event_store):
        self._store = event_store

    def set(self, *, tenant_id: str, key: str, value):
        self._store.set_setting(
            tenant_id=str(tenant_id),
            key=str(key),
            value=value,
        )
