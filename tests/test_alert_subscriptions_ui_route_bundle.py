from pathlib import Path

from interfaces.web.settings.alert_subscriptions_integration.route_bundle import AlertSubscriptionsRouteBundle
from interfaces.web.settings.messaging_preferences_integration.inmemory_settings_gateway import InMemorySettingsGateway


def test_route_bundle_loads_and_saves(tmp_path: Path):
    gw = InMemorySettingsGateway()
    bundle = AlertSubscriptionsRouteBundle(project_root=Path(__file__).resolve().parents[1], settings_gateway=gw)

    page = bundle.model(tenant_id='t1')
    assert page.status_code == 200
    assert page.body['setting_key'] == 'messaging_policy:alert_subscriptions'

    saved = bundle.save(
        tenant_id='t1',
        payload={'items': [{'recipient_user_id': 'ceo-1', 'channel': 'email', 'min_level': 'critical'}]},
    )
    assert saved.status_code == 200
    assert gw.get_value(tenant_id='t1', key='messaging_policy:alert_subscriptions')[0]['channel'] == 'email'
