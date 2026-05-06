from pathlib import Path

from interfaces.web.settings.messaging_preferences_integration.inmemory_settings_gateway import InMemorySettingsGateway
from interfaces.web.settings.messaging_preferences_integration.route_bundle import MessagingPreferencesRouteBundle


def test_route_bundle_serves_model_and_save():
    root = Path.cwd()
    gw = InMemorySettingsGateway()
    bundle = MessagingPreferencesRouteBundle(project_root=root, settings_gateway=gw)

    save = bundle.save(
        tenant_id="tenant-x",
        payload={
            "primary": "email",
            "enabled": ["telegram", "email"],
            "verified": ["email"],
        },
    )
    assert save.status_code == 200
    assert save.body["saved_value"]["primary"] == "email"

    model = bundle.model(tenant_id="tenant-x")
    assert model.status_code == 200
    assert model.body["primary"] == "email"
