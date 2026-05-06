from pathlib import Path


def test_runtime_boot_settings_gateway_uses_common_eventstore_gateway():
    text = Path('runtime/boot/settings/messaging_settings_gateway.py').read_text(encoding='utf-8')
    assert 'build_event_store_settings_gateway' in text
    assert 'messaging_preferences_integration.eventstore_settings_gateway' not in text
