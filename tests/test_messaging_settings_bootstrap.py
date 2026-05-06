from runtime.boot.settings.messaging_settings_gateway import build_messaging_settings_gateway
from runtime.boot.web.runtime_web_attach import attach_runtime_web_bundle
from runtime.boot.web.runtime_web_bundle import RuntimeWebBundle
from runtime.messaging.settings import SETTING_KEY
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _Executor:
    class _Effects:
        pass

    def __init__(self):
        self._effects = self._Effects()


def test_settings_gateway_uses_canonical_event_store_settings_api():
    event_store = MemoryEventStore()
    gateway = build_messaging_settings_gateway(event_store=event_store)
    gateway.set_value(tenant_id='t1', key=SETTING_KEY, value={'primary': 'sms', 'enabled': ['sms']})
    value = gateway.get_value(tenant_id='t1', key=SETTING_KEY)
    assert value == {'primary': 'sms', 'enabled': ['sms']}


def test_runtime_web_bundle_attaches_to_executor_and_effects():
    executor = _Executor()
    gateway = build_messaging_settings_gateway(event_store=MemoryEventStore())
    bundle = attach_runtime_web_bundle(runtime_obj=executor, project_root='.', settings_gateway=gateway)
    assert isinstance(bundle, RuntimeWebBundle)
    assert executor.settings_gateway is gateway
    assert executor._effects.settings_gateway is gateway
    assert executor.web_bundle is bundle
    assert executor._effects.web_bundle is bundle
