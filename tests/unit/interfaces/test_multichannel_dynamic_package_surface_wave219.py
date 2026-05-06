from __future__ import annotations

import importlib

CHANNEL_MODULES=(
    'interfaces.messaging.whatsapp',
    'interfaces.messaging.sms',
    'interfaces.messaging.email',
    'interfaces.messaging.instagram',
    'interfaces.messaging.messenger',
    'interfaces.regional.line',
    'interfaces.regional.wechat',
    'interfaces.regional.kakaotalk',
    'interfaces.regional.viber',
)
EXPECTED_EXPORTS={'Adapter','Runner','build_binding','build_config','delivery_preview','map_result','normalize_inbound','send_raw','sender_identity'}

def test_channel_packages_export_expected_dynamic_surface():
    for mod_name in CHANNEL_MODULES:
        mod=importlib.import_module(mod_name)
        assert set(mod.__all__) == EXPECTED_EXPORTS, mod_name

def test_channel_packages_expose_constructible_runner_and_adapter():
    for mod_name in CHANNEL_MODULES:
        mod=importlib.import_module(mod_name)
        assert mod.Runner() is not None, mod_name
        assert mod.Adapter() is not None, mod_name

def test_channel_packages_expose_callable_surface_members():
    for mod_name in CHANNEL_MODULES:
        mod=importlib.import_module(mod_name)
        for name in ('build_binding','build_config','delivery_preview','map_result','normalize_inbound','send_raw','sender_identity'):
            assert callable(getattr(mod, name)), (mod_name, name)
