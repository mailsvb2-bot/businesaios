from interfaces.web.settings.common.eventstore_settings_gateway import EventStoreSettingsGateway
from runtime.settings.event_store_gateway import build_event_store_settings_gateway


class _Store:
    def __init__(self):
        self.values = {}

    def get_setting(self, *, tenant_id: str, key: str):
        return self.values.get((tenant_id, key))

    def set_setting(self, *, tenant_id: str, key: str, value):
        self.values[(tenant_id, key)] = value


def test_build_event_store_settings_gateway_uses_common_gateway_surface():
    gateway = build_event_store_settings_gateway(event_store=_Store())
    assert isinstance(gateway, EventStoreSettingsGateway)
    gateway.set_value(tenant_id='t1', key='k', value={'x': 1})
    assert gateway.get_value(tenant_id='t1', key='k') == {'x': 1}
