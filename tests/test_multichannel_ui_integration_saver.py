from interfaces.web.settings.common.save_command import SaveCommand
from interfaces.web.settings.messaging_preferences_integration.inmemory_settings_gateway import InMemorySettingsGateway
from interfaces.web.settings.messaging_preferences_integration.save_controller import SaveController


def test_save_controller_persists_saved_value():
    gw = InMemorySettingsGateway()
    controller = SaveController(settings_gateway=gw)

    out = controller.save(
        SaveCommand(
            tenant_id="t1",
            payload={
                "primary": "whatsapp",
                "enabled": ["telegram", "whatsapp"],
                "verified": ["whatsapp"],
            },
        )
    ).body

    assert out["saved_value"]["primary"] == "whatsapp"

    stored = gw.get_value(tenant_id="t1", key="messaging:channel_preference")
    assert stored["primary"] == "whatsapp"
    assert stored["enabled"] == ["whatsapp", "telegram"]
