from __future__ import annotations

from interfaces.web.settings.common.eventstore_settings_gateway import EventStoreSettingsGateway
from runtime.settings.event_store_reader import EventStoreSettingsReader
from runtime.settings.event_store_writer import EventStoreSettingsWriter
from runtime.settings.settings_service import SettingsService


def build_event_store_settings_gateway(*, event_store):
    reader = EventStoreSettingsReader(event_store=event_store)
    writer = EventStoreSettingsWriter(event_store=event_store)
    service = SettingsService(reader=reader, writer=writer)
    return EventStoreSettingsGateway(settings_service=service)
