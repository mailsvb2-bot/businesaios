from pathlib import Path

from interfaces.web.settings.messaging_preferences_integration.inmemory_settings_gateway import InMemorySettingsGateway
from interfaces.web.settings.messaging_preferences_integration.route_bundle import MessagingPreferencesRouteBundle


def test_route_bundle_html_contains_expected_assets():
    root = Path.cwd()
    gw = InMemorySettingsGateway()
    bundle = MessagingPreferencesRouteBundle(project_root=root, settings_gateway=gw)

    out = bundle.html()
    assert out.status_code == 200
    assert "channel_preferences.css" in out.body
    assert "channel_preferences.js" in out.body
