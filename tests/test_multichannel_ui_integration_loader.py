from interfaces.web.settings.common.page_query import PageQuery
from interfaces.web.settings.messaging_preferences_integration.inmemory_settings_gateway import InMemorySettingsGateway
from interfaces.web.settings.messaging_preferences_integration.page_controller import PageController


def test_page_controller_reads_existing_value_from_gateway():
    gw = InMemorySettingsGateway()
    gw.set_value(
        tenant_id="t1",
        key="messaging:channel_preference",
        value={"primary": "email", "enabled": ["telegram", "email"], "verified": ["email"]},
    )

    controller = PageController(settings_gateway=gw)
    out = controller.get_model(PageQuery(tenant_id="t1")).body

    assert out["primary"] == "email"
    assert "email" in out["enabled"]
    assert "email" in out["verified"]
