from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.settings.settings_service import SettingsService


class EventStoreSettingsGateway:
    """Canonical settings gateway backed by the event-store settings service."""

    def __init__(self, *, settings_service: SettingsService):
        self._service = settings_service

    def get_value(self, *, tenant_id: str, key: str):
        return self._service.get(
            tenant_id=str(tenant_id),
            key=str(key),
        )

    def set_value(self, *, tenant_id: str, key: str, value):
        self._service.set(
            tenant_id=str(tenant_id),
            key=str(key),
            value=value,
        )
