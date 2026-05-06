from __future__ import annotations

from pathlib import Path

from canon.collapse_readiness import CORE_RUNTIME_COLLAPSED_SURFACES


def _read(relative: str) -> str:
    return Path(relative).read_text(encoding='utf-8')


def test_multichannel_shims_are_marked_collapsed_to_runtime_owners() -> None:
    assert CORE_RUNTIME_COLLAPSED_SURFACES['interfaces.multichannel.bridge'] == 'runtime.messaging.bridge'
    assert CORE_RUNTIME_COLLAPSED_SURFACES['interfaces.multichannel.results'] == 'runtime.messaging.delivery_result'


def test_internal_transport_uses_runtime_multichannel_owners() -> None:
    text = _read('runtime/_internal/effects_actions/telegram/messaging_parts/transport.py')
    assert 'interfaces.multichannel.bridge' not in text
    assert 'interfaces.multichannel.results' not in text
    assert 'from runtime.messaging.bridge import get_multichannel_effects_bridge' in text
    assert 'from runtime.messaging.delivery_result import DeliveryResult' in text


def test_multichannel_shims_stay_thin_compat_surfaces() -> None:
    bridge = _read('interfaces/multichannel/bridge.py')
    results = _read('interfaces/multichannel/results.py')
    assert 'CANON_COMPAT_SHIM = True' in bridge
    assert 'from runtime.messaging.bridge import MultiChannelEffectsBridge, get_multichannel_effects_bridge' in bridge
    assert 'CANON_COMPAT_SHIM = True' in results
    assert 'from runtime.messaging.delivery_result import DeliveryResult' in results


SETTINGS_REMOVED_SHIMS = ['interfaces/web/settings/messaging_preferences_integration/http_payload_reader.py', 'interfaces/web/settings/messaging_preferences_integration/page_query.py', 'interfaces/web/settings/messaging_preferences_integration/save_command.py', 'interfaces/web/settings/messaging_preferences_integration/settings_gateway_protocol.py', 'interfaces/web/settings/messaging_preferences_integration/static_asset_reader.py', 'interfaces/web/settings/messaging_preferences_integration/tenant_reader.py', 'interfaces/web/settings/alert_subscriptions_integration/http_payload_reader.py', 'interfaces/web/settings/alert_subscriptions_integration/page_query.py', 'interfaces/web/settings/alert_subscriptions_integration/save_command.py', 'interfaces/web/settings/alert_subscriptions_integration/settings_gateway_protocol.py', 'interfaces/web/settings/alert_subscriptions_integration/static_asset_reader.py', 'interfaces/web/settings/alert_subscriptions_integration/tenant_reader.py', 'interfaces/web/settings/common/http_response.py']


def test_settings_shim_files_are_removed_after_owner_collapse() -> None:
    for relative in SETTINGS_REMOVED_SHIMS:
        assert not Path(relative).exists(), relative


def test_internal_settings_integration_code_uses_common_owners() -> None:
    checked = {
        'interfaces/web/settings/messaging_preferences_integration/static_controller.py': [
            'interfaces.web.common.http_response',
            'interfaces.web.settings.common.static_asset_reader',
        ],
        'interfaces/web/settings/messaging_preferences_integration/save_controller.py': [
            'interfaces.web.common.http_response',
            'interfaces.web.settings.common.save_command',
        ],
        'interfaces/web/settings/messaging_preferences_integration/route_bundle.py': [
            'interfaces.web.settings.common.http_payload_reader',
            'interfaces.web.settings.common.page_query',
            'interfaces.web.settings.common.save_command',
            'interfaces.web.settings.common.tenant_reader',
        ],
        'interfaces/web/settings/alert_subscriptions_integration/save_controller.py': [
            'interfaces.web.common.http_response',
            'interfaces.web.settings.common.save_command',
        ],
        'interfaces/web/settings/alert_subscriptions_integration/route_bundle.py': [
            'interfaces.web.settings.common.http_payload_reader',
            'interfaces.web.settings.common.page_query',
            'interfaces.web.settings.common.save_command',
            'interfaces.web.settings.common.tenant_reader',
        ],
        'interfaces/web/settings/common/__init__.py': [
            'interfaces.web.common.http_response',
        ],
    }
    for relative, required_imports in checked.items():
        text = _read(relative)
        assert '.integration.http_response' not in text
        assert '.integration.http_payload_reader' not in text
        assert '.integration.page_query' not in text
        assert '.integration.save_command' not in text
        assert '.integration.tenant_reader' not in text
        for required in required_imports:
            assert required in text, (relative, required)
