from __future__ import annotations


class EventStoreSettingsReader:

    def __init__(self, *, event_store):
        self._store = event_store

    def get(self, *, tenant_id: str, key: str):
        return self._store.get_setting(
            tenant_id=str(tenant_id),
            key=str(key),
        )
