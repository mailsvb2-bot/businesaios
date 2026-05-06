from __future__ import annotations

from runtime.settings.settings_reader import SettingsReader
from runtime.settings.settings_writer import SettingsWriter


class SettingsService:

    def __init__(self, *, reader: SettingsReader, writer: SettingsWriter):
        self._reader = reader
        self._writer = writer

    def get(self, *, tenant_id: str, key: str):
        return self._reader.get(
            tenant_id=str(tenant_id),
            key=str(key),
        )

    def set(self, *, tenant_id: str, key: str, value):
        self._writer.set(
            tenant_id=str(tenant_id),
            key=str(key),
            value=value,
        )
